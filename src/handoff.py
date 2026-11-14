"""Step 4: non-destructive, geometry-cached, pixel-art handoff.

An artist handoff holds one immutable raycast result per view. Relighting and
material suggestions operate on these surface buffers only: no geometry builder
or raycast is called by :func:`grade`. Sprite geometry remains 1x DOS-indexed.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
from typing import Any

import numpy as np
from PIL import Image

from .architectural_renderer import cast
from .geometry import MATERIAL_IDS, VisibleSurfaces
from .lighting import SUN_FIVE, shade, quantize
from .palette import load_palette, ramp, save_indexed
from .pipeline import load_scene

ANGLES = (0, 90, 180, 270)
DEFAULT_PROFILES = ("painted_steel", "brick_concrete", "brick_steel")


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf8")


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_presets(path=None):
    text = Path(path).read_text(encoding="utf8") if path else (Path(__file__).resolve().parents[1] / "data" / "handoff_profiles.json").read_text(encoding="utf8")
    config = json.loads(text)
    if config.get("schema_version") != 1 or not config.get("ramps") or not config.get("profiles"):
        raise ValueError("Expected schema_version=1, ramps and profiles")
    for name, values in config["ramps"].items():
        if len(values) != 4 or any(len(v) != 3 or any(not (0 <= x <= 255) for x in v) for v in values):
            raise ValueError(f"Ramp {name} must contain exactly four RGB triples")
    for name, profile in config["profiles"].items():
        for key in ("main_wall", "secondary_wall"):
            if profile.get(key) not in config["ramps"]:
                raise ValueError(f"Profile {name} has unknown {key} ramp")
        for color_name in profile.get("materials", {}).values():
            if color_name not in config["ramps"]:
                raise ValueError(f"Profile {name} has unknown material ramp {color_name}")
    return config


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf8") != payload:
            raise ValueError(f"Refusing to overwrite changed record: {path}")
    else:
        path.write_text(payload, encoding="utf8")


def _save_npz_once(path: Path, surface: VisibleSurfaces):
    if path.exists():
        existing = VisibleSurfaces.read(path)
        if existing.digest() != surface.digest():
            raise ValueError(f"Existing geometry differs: {path}")
        return
    np.savez_compressed(path, material=surface.material, normal=surface.normal,
                        depth=surface.depth, primitive=surface.primitive,
                        shaded=surface.reference_pixels)


def _light_bands(surface: VisibleSurfaces, light):
    # Share the renderer's lighting quantisation; a material/lighting branch
    # must never interpret roof slopes differently from the base renderer.
    return quantize(surface, light)


def _zones(surface, metadata):
    """Create semantic pixel masks from true 3D primitive ownership, not UVs."""
    names = {int(k): v for k, v in metadata["primitive_components"].items()}
    hosts = set(metadata["fabric_components"])
    masks = {name: np.zeros(surface.material.shape, dtype=bool) for name in
             ("main_wall", "secondary_wall", "roof", "metal", "concrete", "frame", "glass", "chimney", "pipe")}
    # A primitive can now expose several physical materials (for example the
    # steel-clad vertical triangle beneath a gable roof versus its roof slopes).
    # Split by (primitive, material) rather than examining just one first
    # pixel; that old shortcut silently assigned an entire roof to one zone.
    for pid in np.unique(surface.primitive[surface.silhouette]):
        i = int(pid)
        component = names.get(i)
        owner = surface.primitive == i
        for name,mid in MATERIAL_IDS.items():
            pixels = owner & (surface.material == mid)
            if not pixels.any():
                continue
            if component in hosts and name in ('metal','concrete'):
                zone = 'main_wall' if component == 'main' else 'secondary_wall'
            else:
                zone = 'pipe' if name == 'tank_wall' else name
            masks[zone][pixels] = True
    coverage = sum(mask.astype(np.uint8) for mask in masks.values())
    if not np.all(coverage[surface.silhouette] == 1) or np.any(coverage[~surface.silhouette]):
        raise AssertionError("Semantic masks must partition exactly the visible silhouette")
    return masks


def _profile_pixels(surface, metadata, bands, profile, config, palette):
    masks = _zones(surface, metadata)
    indices = np.zeros_like(surface.reference_pixels)
    for zone, mask in masks.items():
        if not mask.any():
            continue
        which = profile[zone] if zone in ("main_wall", "secondary_wall") else profile.get("materials", {}).get(zone, zone)
        if which == zone and which not in config["ramps"]:
            raise ValueError(f"Profile does not define {zone} and no matching ramp exists")
        values = ramp(config["ramps"][which], palette)
        indices[mask] = values[bands[mask]]
    if not np.array_equal(indices != 0, surface.silhouette):
        raise AssertionError("Colour treatments must preserve every geometry pixel")
    return indices, masks


def _write_mask_png(dest, mask):
    dest = Path(dest)
    if dest.exists():
        previous = np.asarray(Image.open(dest))
        if not np.array_equal(previous != 0, mask):
            raise ValueError(f"Mask already exists with different pixels: {dest}")
    else:
        Image.fromarray((mask.astype(np.uint8) * 255), mode="L").save(dest)


def _make_guides(view, surface: VisibleSurfaces, masks):
    palette = load_palette()
    # Exact binary selection masks for Photoshop channels (white=selected).
    masks_folder = view / "masks"
    masks_folder.mkdir(exist_ok=True)
    _write_mask_png(masks_folder / "silhouette.png", surface.silhouette)
    for name, mask in masks.items():
        _write_mask_png(masks_folder / f"{name}.png", mask)
    guides = view / "guides"
    guides.mkdir(exist_ok=True)
    norm = (np.clip(surface.normal, -1, 1) * .5 + .5) * 255
    rgb = np.clip(np.rint(norm), 0, 255).astype(np.uint8)
    rgb[~surface.silhouette] = 0
    Image.fromarray(rgb, mode="RGB").save(guides / "normal_preview.png")
    depth = surface.depth
    vis = depth[surface.silhouette]
    depth8 = np.zeros(depth.shape, dtype=np.uint8)
    if vis.size:
        lo, hi = float(np.min(vis)), float(np.max(vis))
        if hi > lo:
            depth8[surface.silhouette] = np.clip(np.rint(40 + 215 * (hi - vis) / (hi - lo)), 0, 255).astype(np.uint8)
        else:
            depth8[surface.silhouette] = 255
    Image.fromarray(depth8, mode="L").save(guides / "depth_preview.png")
    Image.fromarray(surface.primitive.astype(np.uint16)).save(guides / "primitive_id.tif")
    Image.fromarray(surface.material, mode="L").save(guides / "material_id.png")


def _grade_view(view, light, name, presets, profile_names):
    view = Path(view)
    surface = VisibleSurfaces.read(view / "geometry.npz")
    metadata = json.loads((view / "primitive_map.json").read_text(encoding="utf8"))
    config = _load_presets(presets)
    for profile in profile_names:
        if profile not in config["profiles"]:
            raise ValueError(f"Unknown profile: {profile} (available: {list(config['profiles'])})")
    bands = _light_bands(surface, light)
    palette = load_palette()
    ref = surface.reference_pixels
    identity = _hash_bytes(_canonical({"geometry": surface.digest(), "light": list(light), "name": name,
                                       "profiles": list(profile_names), "profile_config": config}))[:16]
    dest = view / "treatments" / identity
    dest.mkdir(parents=True, exist_ok=True)
    # Exact original shader output is never changed; independent lighting variant.
    standard = shade(surface, palette, light)
    masks = _zones(surface, metadata)
    save_indexed(dest / "lighting.png", standard, palette)
    outputs = {}
    for profile in profile_names:
        pixels, _ = _profile_pixels(surface, metadata, bands, config["profiles"][profile], config, palette)
        save_indexed(dest / f"{profile}.png", pixels, palette)
        outputs[profile] = _hash_bytes(pixels.tobytes())
    _make_guides(view, surface, masks)
    record = {"schema_version":1, "id": identity, "geometry_sha256":surface.digest(),
              "source_pixel_sha256":_hash_bytes(ref.tobytes()), "sun_world":list(light),
              "profiles": list(profile_names), "profile_config_sha256":_hash_bytes(_canonical(config)),
              "pixel_sha256_by_profile":outputs,
              "paths":{"lighting":str((dest/"lighting.png").relative_to(view)),
                       "colour":{p:str((dest/f"{p}.png").relative_to(view)) for p in profile_names}}}
    _write_json(dest / "manifest.json", record)
    return record


def prepare(run, output, candidates=None, *, preset_path=None, profile_names=DEFAULT_PROFILES,
            light=SUN_FIVE):
    """Prepare artists' cached geometry and first lighting/material branches."""
    run = Path(run)
    out = Path(output)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf8"))
    selected = sorted(manifest["candidates"]) if candidates is None else list(candidates)
    if not selected:
        raise ValueError("No candidates selected")
    out.mkdir(parents=True, exist_ok=True)
    palette = load_palette()
    palette_path = out / "palette.act"
    if palette_path.exists() and palette_path.read_bytes() != bytes(palette):
        raise ValueError("Handoff contains a different palette")
    if not palette_path.exists():
        palette_path.write_bytes(bytes(palette))
    manifest_out = {"schema_version":1, "compiler":"becher-step4", "source_seed":manifest.get("seed"),
                    "palette_sha256":_hash_bytes(bytes(palette)), "candidates":{}}
    manifest_file = out / "manifest.json"
    if manifest_file.exists():
        old = json.loads(manifest_file.read_text(encoding="utf8"))
        if {k:v for k,v in old.items() if k != "candidates"} != {k:v for k,v in manifest_out.items() if k != "candidates"}:
            raise ValueError("Handoff cannot combine different source seeds or palettes")
        manifest_out["candidates"] = dict(old["candidates"])
    for candidate_id in selected:
        if candidate_id not in manifest["candidates"]:
            raise ValueError(f"Unknown candidate: {candidate_id}")
        chosen = manifest["candidates"][candidate_id]
        node = chosen["current"]
        model = load_scene(run, node)
        where = out / f"candidate_{candidate_id}"
        where.mkdir(parents=True, exist_ok=True)
        _write_json(where / "scene.json", model.to_dict())
        rec = {"node":node, "family":model.family, "scene_sha256":_hash_bytes(_canonical(model.to_dict())),
               "views":{}}
        for angle in ANGLES:
            view = where / f"r{angle:03d}"
            view.mkdir(parents=True, exist_ok=True)
            file = view / "geometry.npz"
            mapfile = view / "primitive_map.json"
            if file.exists() and mapfile.exists():
                surfaces = VisibleSurfaces.read(file)
            else:
                surfaces, metrics = cast(model, angle)
                _save_npz_once(file, surfaces)
                _write_json(mapfile, {"primitive_components":metrics["primitive_components"],
                           "primitive_materials":metrics["primitive_materials"],
                           "fabric_components":[c.id for c in model.components if c.role=="fabric"]})
            source_png = view / "shaded_original.png"
            if source_png.exists():
                from .palette import open_indexed
                if not np.array_equal(open_indexed(source_png,palette),surfaces.reference_pixels):
                    raise ValueError(f"Protected source differs: {source_png}")
            else:
                save_indexed(source_png,surfaces.reference_pixels,palette)
            # Untouched editable paint data: empty indexed layer with 0 meaning no change.
            paint_layer = view / "artist_layer.png"
            if not paint_layer.exists():
                save_indexed(paint_layer,np.zeros_like(surfaces.reference_pixels),palette)
            # RGBA artist overlay works with ordinary Photoshop RGB layers.
            rgba_layer = view / "artist_rgba.png"
            if not rgba_layer.exists():
                Image.new("RGBA", (64,128), (0,0,0,0)).save(rgba_layer)
            jsx = view / "open_in_photoshop.jsx"
            if not jsx.exists():
                jsx.write_text('#target photoshop\n// Open this script in Photoshop (File > Scripts > Browse).\n// The source sprite is converted to RGB so Photoshop can use layers.\n// Draw on the named paint layer. Export ONLY that layer as a 64x128\n// RGBA PNG with fully transparent untouched pixels, then use\n// becher import-paint to return to the exact TTD DOS palette.\n(function () {\n    var root = File($.fileName).parent;\n    var doc = app.open(File(root.fsName + "/shaded_original.png"));\n    doc.changeMode(ChangeMode.RGB);\n    var paint = doc.artLayers.add();\n    paint.name = "Artist paint - export this layer as RGBA PNG";\n})();\n', encoding="utf8")
            treatment = _grade_view(view,light,"default",preset_path,profile_names)
            rec["views"][f"{angle:03d}"] = {"geometry_sha256":surfaces.digest(),
                                          "source":str(source_png.relative_to(out)),
                                          "treatment":treatment["id"]}
        if candidate_id in manifest_out["candidates"] and manifest_out["candidates"][candidate_id] != rec:
            raise ValueError(f"Candidate {candidate_id} changed; choose a different --out path")
        manifest_out["candidates"][candidate_id] = rec
    if manifest_file.exists():
        # Add new candidate records without modifying existing records/art layers.
        payload = json.dumps(manifest_out,indent=2,sort_keys=True,ensure_ascii=False) + "\n"
        if manifest_file.read_text(encoding="utf8") != payload:
            manifest_file.write_text(payload,encoding="utf8")
    else:
        _write_json(manifest_file,manifest_out)
    return {"candidates":len(selected),"sprites":4*len(selected),
            "material_profiles":list(profile_names),"out":str(out)}


def grade(output, *, candidate=None, light=SUN_FIVE, profile_names=DEFAULT_PROFILES,
          preset_path=None, name="variant"):
    """Branch solely from frozen g-buffers: no scene compiler or raycasting."""
    out = Path(output)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf8"))
    selected = sorted(manifest["candidates"]) if candidate is None else [candidate]
    if any(c not in manifest["candidates"] for c in selected):
        raise ValueError("Unknown candidate")
    results = []
    for cid in selected:
        for angle in ANGLES:
            view = out / f"candidate_{cid}" / f"r{angle:03d}"
            results.append(_grade_view(view,light,name,preset_path,profile_names))
    return {"candidates":len(selected),"sprites":len(results),
            "branch_ids":sorted({r["id"] for r in results}), "out":str(out)}
