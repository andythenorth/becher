"""Serve the local Becher assembly batch UI."""

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


@dataclass(frozen=True)
class Batch:
    id: str
    sprites: dict
    generated: tuple = ()
    compose_args: tuple = ()
    revisions: tuple = ()

    def response(self):
        labels = {entry["id"]: entry["label"] for entry in self.generated}
        return {
            "id": self.id,
            "can_reroll": bool(self.compose_args),
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
        self.galleries = {}
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

    def render_component(self, data):
        component = data.get("component")
        if not isinstance(component, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_]*", component):
            raise ValueError("Select an installed component")
        batch_id = uuid4().hex
        output = self.scratch / batch_id
        with self.lock:
            self.command("render-component", "--component", component, "--out", str(output))
            sprites = {component: {angle: output / f"r{angle:03d}.png" for angle in ROTATIONS}}
            batch = Batch(batch_id, sprites)
            self.batches[batch_id] = batch
            return batch

    def render_component_sheets(self):
        gallery_id = uuid4().hex
        output = self.scratch / f"component-sheets-{gallery_id}"
        result = json.loads(self.command("component-sheets", "--out", str(output)))
        with self.lock:
            self.galleries[gallery_id] = {item["name"]: output / item["name"]
                                          for item in result["sheets"]}
        result["sheets"] = [dict(item, url=f"/component-gallery/{gallery_id}/{item['name']}")
                            for item in result["sheets"]]
        return result

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
            batch = Batch(batch_id, sprites, entries, args, (0,) * len(entries))
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
            batch_id, {**batch.sprites, **sprites},
            batch.generated[:index] + entries + batch.generated[index+1:],
            batch.compose_args, batch.revisions[:index] + (revision,) + batch.revisions[index+1:],
        )
        self.batches[batch_id] = updated
        return updated

    def reroll(self, data):
        with self.lock:
            batch = self.get(data.get("batch"))
            if not batch.compose_args:
                raise ValueError("Reroll is available for generated batches")
            return self.reroll_composition(batch, data.get("candidate"))

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
                filename = f"{candidate}_{path.name}"
                if url.query != "download":
                    filename = None
                self.send_bytes(path.read_bytes(), "image/png", filename)
                return

            match = re.fullmatch(r"/component-gallery/([a-f0-9]+)/([a-z0-9-]+\.png)", url.path)
            if match:
                gallery_id, filename = match.groups()
                path = self.server.review.galleries[gallery_id][filename]
                download = filename if url.query == "download" else None
                self.send_bytes(path.read_bytes(), "image/png", download)
                return

            match = re.fullmatch(r"/batch/([a-f0-9]+)\.zip", url.path)
            if match:
                batch = self.server.review.get(match[1])
                stream = BytesIO()
                with ZipFile(stream, "w", compression=ZIP_STORED) as archive:
                    for key, sprites in batch.sprites.items():
                        for sprite in sprites.values():
                            name = f"{key}_{sprite.name}"
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
        actions = {"/reroll": self.server.review.reroll,
                   "/render-component": self.server.review.render_component,
                   "/component-sheets": lambda _data: self.server.review.render_component_sheets(),
                   "/compose": self.server.review.compose}
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
            result = actions[self.path](data)
            response = result.response() if isinstance(result, Batch) else result
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
