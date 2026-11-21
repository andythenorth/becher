"""New headframe variants are legitimate assemblies with four readable sprite views."""

import numpy as np
import pytest
from src.composition import load_part, vocabularies, arbitrary_scene
from src.geometry import MATERIAL_IDS
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh

NAMES = (
    "quarry_headframe_compact_low",
    "quarry_headframe_tall_narrow",
    "quarry_headframe_wide_heavy",
    "quarry_headframe_enclosed_winder",
    "quarry_headframe_deep_twin",
    "quarry_headframe_open_gantry",
)

@pytest.mark.parametrize("name", NAMES)
def test_headframe_is_selectable_and_renders_at_all_rotations(name):
    assert name in vocabularies()["Mining and aggregates"]["annexes"]
    part = load_part(name)
    assert part["role"] == "structure"
    assert len({s["id"] for s in part["shapes"]}) == len(part["shapes"])
    assert all(s["material"] in MATERIAL_IDS for s in part["shapes"])
    assert -0.5 <= part["footprint"][0] < part["footprint"][2] <= 0.5
    assert -0.5 <= part["footprint"][1] < part["footprint"][3] <= 0.5
    # The real composition path, including slab and placement clearance.
    scene = arbitrary_scene([(name, 0.5, 0.5, 0)], {name: part})
    assert scene["catalogue"]["silhouette"] == "high"
    mesh = compile_scene(scene)
    for rotation in (0, 90, 180, 270):
        surf, metrics = cast_mesh(mesh, rotation)
        assert surf.reference_pixels.shape == (128, 64)
        assert np.count_nonzero(surf.reference_pixels > 0) > 100
        assert metrics["visible_primitive_ids"] >= 4

def test_deep_twin_and_open_gantry_have_different_top_structures():
    twin = load_part("quarry_headframe_deep_twin")
    gantry = load_part("quarry_headframe_open_gantry")
    assert sum(s["id"].startswith("gear_housing_") for s in twin["shapes"]) == 2
    assert sum(s["id"].startswith("gear_cap_") for s in twin["shapes"]) == 2
    assert any(s["id"] == "exposed_hoist_sheave" and s["type"] == "rings" for s in gantry["shapes"])
