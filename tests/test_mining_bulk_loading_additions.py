"""Mining and bulk-loading source assemblies: selectable and native-view safe."""

import numpy as np
import pytest

from src.composition import arbitrary_scene, candidates, load_part, vocabularies
from src.geometry import MATERIAL_IDS
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh

MINING = (
    "mine_washery_gallery",
    "mine_crusher_house_heavy",
    "mine_sorting_tower_sidebay",
    "mine_screening_shed_low",
    "mine_coal_breaker_asymmetric",
    "mine_screen_hall_massive",
    "mine_screen_hall_grounded",
)
BULK = (
    "bulk_rail_bunker_piers",
    "bulk_hopper_house_heavy",
    "bulk_coal_tipple_grounded",
    "bulk_loading_building_bays",
    "bulk_bunker_massive_buttress",
    "bulk_narrow_charging_tower",
)


@pytest.mark.parametrize("name", MINING + BULK)
def test_new_assemblies_compile_and_render_all_rotations(name):
    part = load_part(name)
    assert part["role"] in {"structure", "shed"}
    assert len(part["shapes"]) >= 4
    assert len({shape["id"] for shape in part["shapes"]}) == len(part["shapes"])
    assert all(shape["material"] in MATERIAL_IDS for shape in part["shapes"])
    x0, y0, x1, y1 = part["footprint"]
    assert -0.5 < x0 < x1 < 0.5 and -0.5 < y0 < y1 < 0.5
    scene = arbitrary_scene([(name, 0.5, 0.5, 0)], {name: part})
    mesh = compile_scene(scene)
    for angle in (0, 90, 180, 270):
        surface, metrics = cast_mesh(mesh, angle)
        assert surface.reference_pixels.shape == (128, 64)
        assert np.count_nonzero(surface.reference_pixels) > 100
        assert metrics["visible_primitive_ids"] >= 3
        foreground = surface.reference_pixels != 0
        # No visible clipping at the output canvas edges.
        assert not foreground[0].any()
        assert not foreground[-1].any()
        assert not foreground[:, 0].any()
        assert not foreground[:, -1].any()


def test_reviewed_vocabulary_choices():
    groups = vocabularies()
    mining = {name for members in groups["Mining and aggregates"].values() for name in members}
    bulk = {name for members in groups["Bulk loading and bunkers"].values() for name in members}
    assert set(MINING) <= mining
    assert set(BULK) <= bulk
    assert "bulk_double_pier_hopper" not in bulk
    assert "bulk_trapezoid_wagon_bunker" not in bulk
    assert "mine_coal_breaker_stepped" not in mining
    assert "mine_screen_house_stepped" not in mining
    assert "mine_elevated_screen_hall" not in mining
    assert "Dry material handling" in groups


def test_compositions_from_new_group_and_mixed_selection():
    for tags in (["Mining and aggregates"], ["Bulk loading and bunkers"],
                 ["Mining and aggregates", "Bulk loading and bunkers"],
                 ["Bulk loading and bunkers", "Dry material handling"]):
        pool = candidates(tags, "high")
        assert pool, tags
    # An existing light loading annex makes the new vocabulary valid when
    # the user chooses low; the new bunker geometries are deliberately large.
    assert candidates(["Bulk loading and bunkers"], "low")
