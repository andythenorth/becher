"""Bund tanks have a planar cylindrical wall and a distinct top shoulder."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from src.composition import load_part, rigid_place
from src.geometry import MATERIAL_IDS
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh
from src.colour_suggestions import recolour


ROOT = Path(__file__).resolve().parents[1] / 'data' / 'assemblies'
BUND_TANKS = sorted(path.stem for path in ROOT.glob('liquid_pipe_bund_*.json'))


@pytest.mark.parametrize('component', BUND_TANKS)
def test_bund_tank_shoulder_is_creased_without_changing_geometry(component):
    part = load_part(component)
    tank = next(shape for shape in part['shapes'] if shape['id'] == 'tank')
    assert tank['type'] == 'revolution'
    assert tank['material'] == 'tank_wall'
    assert tank['crease_rings'] == [1]
    assert tank['profile'][0][1] == tank['profile'][1][1]
    assert tank['profile'][2][1] < tank['profile'][1][1]

    # The mesh vertices, material IDs and occupied pixels must not change:
    original = deepcopy(part)
    del next(shape for shape in original['shapes'] if shape['id'] == 'tank')['crease_rings']
    new_mesh = compile_scene({'shapes': rigid_place(part, '', (.5, .5))})
    old_mesh = compile_scene({'shapes': rigid_place(original, '', (.5, .5))})
    assert np.array_equal(new_mesh.vertices, old_mesh.vertices)
    assert np.array_equal(new_mesh.materials, old_mesh.materials)
    assert not np.array_equal(new_mesh.normals, old_mesh.normals)

    for rotation in (0, 90, 180, 270):
        new, _ = cast_mesh(new_mesh, rotation)
        old, _ = cast_mesh(old_mesh, rotation)
        assert np.array_equal(new.silhouette, old.silhouette)
        assert np.array_equal(new.material, old.material)
        assert np.array_equal(new.primitive, old.primitive)
        vessel = new.material == MATERIAL_IDS['tank_wall']
        assert vessel.any()
        assert np.any(recolour(new, rotation, 'blue_cladding')[vessel] !=
                      recolour(old, rotation, 'blue_cladding')[vessel])
