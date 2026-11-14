import numpy as np
import pytest

from src.geometry import MATERIAL_IDS
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_large_tank_wall_uses_full_dos_ramp(angle):
    wall = {
        "id": "wall",
        "type": "revolution",
        "profile": [[.04, .29], [.42, .29]],
    }
    lid = {
        "id": "lid",
        "type": "revolution",
        "material": "metal",
        "profile": [[.417, .29], [.44, .29]],
    }
    previous = compile_scene({"shapes": [{**wall, "material": "pipe"}, lid]})
    current = compile_scene({"shapes": [{**wall, "material": "tank_wall"}, lid]})
    before, _ = cast_mesh(previous, angle)
    after, _ = cast_mesh(current, angle)

    wall_pixels = after.material == MATERIAL_IDS["tank_wall"]
    assert set(after.reference_pixels[wall_pixels]) == set(range(96, 104))
    assert np.array_equal(before.reference_pixels[~wall_pixels],
                          after.reference_pixels[~wall_pixels])
