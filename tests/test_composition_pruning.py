"""Regression checks for sound footprint pruning and rigid placement copies."""

import json

from src import composition


def test_impossible_pair_is_rejected_before_expensive_placement(monkeypatch):
    def large_part(name):
        return {
            "footprint": [-.28, -.28, .28, .28],
            "shapes": [
                {"id": name, "type": "box", "material": "metal",
                 "bounds": [-.28, -.28, 0, .28, .28, .20]},
            ],
        }

    parts = {name: large_part(name) for name in ("perf_wide_a", "perf_wide_b")}
    monkeypatch.setattr(composition, "load_part", parts.__getitem__)

    original = composition.packed_scene

    def guarded_packing(available, names, turns, axis):
        assert len(names) == 1, "Two .56-tile widths cannot fit with a clearance"
        return original(available, names, turns, axis)

    monkeypatch.setattr(composition, "packed_scene", guarded_packing)
    pool = composition._general_candidates(tuple(parts), "low")
    assert len(pool) == 2
    assert all(len(scene["catalogue"]["components"]) == 1 for scene in pool.values())


def test_rigid_placement_does_not_mutate_source_coordinate_arrays():
    for name in ("storage_tank_full_tile", "quarry_final_balanced_headframe",
                 "liquid_pipe_bund_rect_side_06"):
        part = composition.load_part(name)
        before = json.dumps(part, sort_keys=True)
        placed = composition.rigid_place(part, "item_", (.5, .5), 1)
        assert json.dumps(part, sort_keys=True) == before
        for shape in placed:
            if "bounds" in shape:
                shape["bounds"][0] = -123
            elif shape["type"] == "revolution":
                shape["profile"][0][0] = -123
            elif shape["type"] == "rings":
                shape["rings"][0][0][0] = -123
            elif shape["type"] == "beam":
                shape["start"][0] = -123
        assert json.dumps(part, sort_keys=True) == before
