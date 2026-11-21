"""Tank light response: broad cylindrical side ramps and distinct top faces."""
import numpy as np
import pytest

from src.composition import load_part, rigid_place
from src.geometry import MATERIAL_IDS
from src.lighting import RAMPS
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh
from src.palette import load_palette, ramp


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_bund_tank_top_not_shaded_as_vertical_wall(angle):
    scene = {"shapes": rigid_place(load_part("liquid_pipe_bund_rect_side_06"), "", (.5, .5))}
    surfaces, _ = cast_mesh(compile_scene(scene), angle)
    tank = surfaces.material == MATERIAL_IDS["tank_wall"]
    flat_top = tank & (surfaces.normal[..., 2] > .95)
    straight_wall = tank & (np.abs(surfaces.normal[..., 2]) < .18)

    palette_ramp = ramp(RAMPS["tank_wall"], load_palette())
    assert np.any(flat_top) and np.any(straight_wall)
    assert np.all(surfaces.reference_pixels[flat_top] == palette_ramp[-3])
    assert set(np.unique(surfaces.reference_pixels[straight_wall])) == set(palette_ramp)


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_horizontal_tanks_remain_indexed_and_have_side_variation(angle):
    scene = {"shapes": rigid_place(load_part("storage_tank_horizontal_low_01"), "", (.5, .5))}
    surfaces, _ = cast_mesh(compile_scene(scene), angle)
    tank = surfaces.material == MATERIAL_IDS["tank_wall"]
    assert np.any(tank)
    assert len(np.unique(surfaces.reference_pixels[tank])) >= 5
    assert np.all(surfaces.reference_pixels[~surfaces.silhouette] == 0)
