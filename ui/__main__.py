"""Serve the review UI and invoke Becher's documented pipeline command."""

import argparse
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Lock
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4
from zipfile import ZIP_STORED, ZipFile


ASSETS = Path(__file__).resolve().parent
ROTATIONS = (0, 90, 180, 270)
STAGES = ("windows", "doors", "equipment", "greeble")
EXPORTED_SPRITE = re.compile(r"([0-9]+)_r(000|090|180|270)\.png")


def exported_sprites(output, designs):
    groups = {}
    for path in sorted((output / "sprites").glob("*.png")):
        match = EXPORTED_SPRITE.fullmatch(path.name)
        if not match:
            raise ValueError(f"Unrecognised Becher export filename: {path.name}")
        key, angle = match.groups()
        groups.setdefault(key, {})[int(angle)] = path

    if len(groups) != designs or any(set(images) != set(ROTATIONS) for images in groups.values()):
        raise ValueError(f"Expected {designs} exported candidates with four rotations each")
    return {key: images for key, images in sorted(groups.items(), key=lambda item: int(item[0]))}


@dataclass(frozen=True)
class Options:
    families: tuple[str, ...]
    seed: int
    designs: int
    workers: int
    facade: str
    edge: str
    roof: str

    @classmethod
    def read(cls, data):
        choices = {
            "facade": ("decals", "boxes"),
            "edge": ("on", "off"),
            "roof": ("on", "off"),
        }
        bounds = {"seed": (0, 2**32 - 1), "designs": (1, 256), "workers": (1, 64)}
        for name, allowed in choices.items():
            if data.get(name) not in allowed:
                raise ValueError(f"Invalid {name}: choose from {', '.join(allowed)}")
        for name, (low, high) in bounds.items():
            value = data.get(name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer from {low} to {high}")
        families = data.get("families")
        if not isinstance(families, list) or not families or not all(
            isinstance(family, str) and re.fullmatch(r"[a-z][a-z0-9_]*", family) for family in families
        ):
            raise ValueError("Select at least one candidate family")
        return cls(families=tuple(families), **{key: data[key] for key in (*choices, *bounds)})

    def args(self, output):
        args = [
            "pipeline", "--seed", str(self.seed),
            "--designs", str(self.designs), "--workers", str(self.workers),
            "--facade-mode", self.facade, "--edge-contrast", self.edge,
            "--roof-colours", self.roof, "--no-buffers", "--out", str(output),
        ]
        for family in self.families:
            args.extend(["--family", family])
        return args


@dataclass(frozen=True)
class Batch:
    id: str
    run: Path | None
    sprites: dict
    generated: tuple = ()
    compose_args: tuple = ()
    revisions: tuple = ()

    def response(self):
        labels = {entry["id"]: entry["label"] for entry in self.generated}
        return {
            "id": self.id,
            "can_reroll": self.run is not None or bool(self.compose_args),
            "generated": self.generated,
            "candidates": [
                {"key": key, "label": labels.get(key), "sprites": [
                    {"angle": angle, "url": f"/sprite/{self.sprite_batch(key)}/{key}/{angle}"}
                    for angle in ROTATIONS
                ]}
                for key in self.sprites
            ],
        }


    def sprite_batch(self, key):
        if self.compose_args:
            return self.sprites[key][0].parent.parent.name
        return self.id

class Review:
    def __init__(self, scratch, project):
        self.scratch = scratch
        self.project = project
        self.batches = {}
        self.latest = {}
        self.lock = Lock()

    def command(self, *args):
        result = subprocess.run(
            [sys.executable, "-m", "becher", *args], cwd=self.project,
            capture_output=True, text=True, errors="replace",
        )
        if result.returncode:
            details = result.stderr or result.stdout
            raise ValueError(f"Becher {args[0]} failed.\n{details[-5000:]}")
        return result.stdout

    def export(self, run, designs):
        batch_id = uuid4().hex
        output = self.scratch / batch_id
        self.command("selection", "--run", str(run), "--out", str(output),
                     "--mode", "active", "--no-buffers")
        batch = Batch(batch_id, run, exported_sprites(output, designs))
        self.batches[batch_id] = batch
        self.latest[run] = batch_id
        return batch

    def generate(self, data):
        options = Options.read(data)
        run = self.scratch / uuid4().hex
        with self.lock:
            self.command(*options.args(run))
            return self.export(run, options.designs)

    def render_component(self, data):
        component = data.get("component")
        if not isinstance(component, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_]*", component):
            raise ValueError("Select an installed component")
        batch_id = uuid4().hex
        output = self.scratch / batch_id
        with self.lock:
            self.command("render-component", "--component", component, "--out", str(output))
            sprites = {component: {angle: output / f"r{angle:03d}.png" for angle in ROTATIONS}}
            batch = Batch(batch_id, None, sprites)
            self.batches[batch_id] = batch
            return batch

    def compose(self, data):
        tags = data.get("vocabularies")
        seed = data.get("seed")
        if not isinstance(tags, list) or not tags or not all(isinstance(tag, str) for tag in tags):
            raise ValueError("Choose an assembly vocabulary")
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("Seed must be an integer from 0 to 4294967295")
        silhouette = data.get("silhouette", "low")
        if silhouette not in ("low", "high"):
            raise ValueError("Choose a low or high silhouette")
        args = ("--seed", str(seed), "--silhouette", silhouette,
                *(f"--vocabulary={tag}" for tag in tags))
        with self.lock:
            batch_id = uuid4().hex
            entries, sprites = self.render_composition(batch_id, "compose", args,
                                                       tuple(f"{row:02d}" for row in range(1, 17)))
            batch = Batch(batch_id, None, sprites, entries, args, (0,) * len(entries))
            self.batches[batch_id] = batch
            return batch

    def render_composition(self, batch_id, command, args, rows):
        output = self.scratch / batch_id
        entries = tuple(json.loads(self.command(command, "--out", str(output), *args))["entries"])
        if tuple(entry["id"] for entry in entries) != rows:
            raise ValueError("Becher returned unexpected composition rows")
        sprites = {
            row: {angle: output / row / f"r{angle:03d}.png" for angle in ROTATIONS}
            for row in rows
        }
        for row, images in sprites.items():
            if not (output / row / "scene.json").is_file() or not all(
                image.is_file() for image in images.values()
            ):
                raise ValueError(f"Missing geometry or sprite for row {row}")
        return entries, sprites

    def reroll_composition(self, batch, candidate):
        if not isinstance(candidate, str) or candidate not in batch.sprites:
            raise ValueError("Choose a composition row")
        index = int(candidate) - 1
        revision = batch.revisions[index] + 1
        args = (*batch.compose_args, "--row", candidate, "--revision", str(revision),
                *(f'--current={entry["composition"]}' for entry in batch.generated))
        batch_id = uuid4().hex
        entries, sprites = self.render_composition(batch_id, "reroll-tile", args, (candidate,))
        updated = Batch(
            batch_id, None, {**batch.sprites, **sprites},
            batch.generated[:index] + entries + batch.generated[index+1:],
            batch.compose_args, batch.revisions[:index] + (revision,) + batch.revisions[index+1:],
        )
        self.batches[batch_id] = updated
        return updated

    def reroll(self, data):
        with self.lock:
            batch = self.get(data.get("batch"))
            if batch.compose_args:
                return self.reroll_composition(batch, data.get("candidate"))
            if batch.run is None:
                raise ValueError("Installed geometries are edited in their scene JSON")
            candidate, stage = data.get("candidate"), data.get("stage")
            if not isinstance(candidate, str) or candidate not in batch.sprites or stage not in STAGES:
                raise ValueError("Choose a candidate and a feature to reroll")
            if self.latest[batch.run] != batch.id:
                raise ValueError("This batch has changed. Generate a new batch in this tab to continue.")
            self.command("reroll", "--run", str(batch.run), "--candidate", candidate,
                         "--stage", stage)
            return self.export(batch.run, len(batch.sprites))

    def get(self, batch_id):
        if not isinstance(batch_id, str) or batch_id not in self.batches:
            raise ValueError("Unknown batch")
        return self.batches[batch_id]


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, payload, media, filename=None, status=HTTPStatus.OK):
        self.send_response(status)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(payload)

    def check_host(self):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") in allowed:
            return True
        self.send_error(HTTPStatus.FORBIDDEN)
        return False

    def do_GET(self):
        if not self.check_host():
            return
        url = urlsplit(self.path)
        if url.path == "/":
            self.send_bytes((ASSETS / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if url.path == "/app.js":
            self.send_bytes((ASSETS / "app.js").read_bytes(), "application/javascript; charset=utf-8")
            return
        if url.path in ("/components", "/vocabularies"):
            try:
                body = self.server.review.command(url.path[1:]).encode()
                self.send_bytes(body, "application/json; charset=utf-8")
            except (OSError, ValueError) as error:
                self.send_bytes(json.dumps({"error": str(error)}).encode(),
                                "application/json; charset=utf-8", status=HTTPStatus.BAD_REQUEST)
            return
        try:
            geometry = re.fullmatch(r"/geometry/([a-f0-9]+)/([a-z0-9_]+)", url.path)
            if geometry:
                batch = self.server.review.get(geometry[1])
                key = geometry[2]
                if key in {entry["id"] for entry in batch.generated}:
                    path = batch.sprites[key][0].with_name("scene.json")
                    self.send_bytes(path.read_bytes(), "application/json", f"{key}.json")
                    return
            match = re.fullmatch(r"/sprite/([a-f0-9]+)/([a-z0-9_]+)/(0|90|180|270)", url.path)
            if match:
                batch_id, candidate, angle = match.groups()
                batch = self.server.review.get(batch_id)
                path = batch.sprites[candidate][int(angle)]
                filename = (f"{candidate}_{path.name}" if batch.run is None else path.name)
                if url.query != "download":
                    filename = None
                self.send_bytes(path.read_bytes(), "image/png", filename)
                return

            match = re.fullmatch(r"/batch/([a-f0-9]+)\.zip", url.path)
            if match:
                batch = self.server.review.get(match[1])
                stream = BytesIO()
                with ZipFile(stream, "w", compression=ZIP_STORED) as archive:
                    for key, sprites in batch.sprites.items():
                        for sprite in sprites.values():
                            name = f"{key}_{sprite.name}" if batch.run is None else sprite.name
                            archive.write(sprite, name)
                        if batch.compose_args:
                            archive.write(sprites[0].with_name("scene.json"), f"{key}_scene.json")
                self.send_bytes(stream.getvalue(), "application/zip", "becher-batch.zip")
                return
        except (ValueError, KeyError, FileNotFoundError):
            pass
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if not self.check_host():
            return
        actions = {"/generate": self.server.review.generate, "/reroll": self.server.review.reroll,
                   "/render-component": self.server.review.render_component, "/compose": self.server.review.compose}
        if self.path not in actions:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            start = perf_counter()
            response = actions[self.path](data).response()
            response["server_ms"] = round((perf_counter() - start) * 1000)
            status = HTTPStatus.OK
        except (ValueError, KeyError, OSError) as error:
            response = {"error": str(error)}
            status = HTTPStatus.BAD_REQUEST
        self.send_bytes(json.dumps(response).encode(), "application/json; charset=utf-8", status=status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    with TemporaryDirectory(prefix="becher-ui-") as scratch:
        with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
            server.review = Review(Path(scratch), ASSETS.parent)
            print(f"Open http://127.0.0.1:{server.server_port}/", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
