"""Process gantries are individual, normally placeable pipe-heavy assemblies."""
from functools import lru_cache

import numpy as np
import pytest

from src.composition import (
    component_catalogue,
    load_part,
    packed_scene,
    rigid_place,
    top,
    vocabularies,
)
from src.geometry import MATERIAL_IDS
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh

NEW = (
    'gantry_open_short_low',
    'gantry_stacked_medium',
    'gantry_high_long_pipeway',
    'gantry_vertical_riser_bank',
    'gantry_control_flat_cuboid',
    'gantry_control_gabled',
    'gantry_control_twin_huts',
    'gantry_control_offset_hut',
    'gantry_bridge_two_level',
    'gantry_bridge_side_vessel',
    'gantry_bridge_riser_tank',
    'gantry_bridge_enclosed_bay',
    'gantry_compact_quarter_low',
    'gantry_compact_third_stacked',
    'gantry_compact_riser_tower',
    'gantry_compact_control_pod',
)
REVIEWED = (
    'fluid_control_rack_broad', 'fluid_control_rack_compact',
    'fluid_control_rack_stepped', 'fluid_link_controls_long',
    'fluid_link_controls_short', 'fluid_link_controls_stepped',
    'fluid_open_rack_long', 'fluid_open_rack_low',
    'fluid_open_rack_tiered', 'fluid_twin_halls_parallel',
    'fluid_twin_halls_split', 'fluid_twin_halls_staggered',
)
ALL = REVIEWED + NEW


def test_process_gantry_vocabulary_is_distinct_and_complete():
    groups = vocabularies()
    assert set(groups['Process gantries']['yards']) == set(ALL)
    assert set(ALL) <= set(component_catalogue())
    assert not set(ALL) & set(groups['Liquid processing']['yards'])
    assert all(name not in groups['Liquid storage'].get('yards', ()) for name in ALL)


@pytest.mark.parametrize('name', ALL)
def test_gantry_geometry_and_source_materials(name):
    part = load_part(name)
    assert part['role'] == 'structure'
    assert part.get('placement') != 'tile'  # Offset pairing is allowed.
    x0, y0, x1, y1 = part['footprint']
    assert x0 < x1 and y0 < y1
    assert x1 - x0 < .925 and y1 - y0 < .925
    shapes = part['shapes']
    assert shapes and len({shape['id'] for shape in shapes}) == len(shapes)
    assert all(s['material'] in MATERIAL_IDS for s in shapes)
    assert any(s['material'] == 'pipe' for s in shapes)
    mesh = _mesh(name)
    assert np.isfinite(mesh.vertices).all()
    assert len(mesh.vertices) > 50


@pytest.mark.parametrize('name', NEW)
def test_new_gantries_use_the_existing_round_pipe_primitive(name):
    shapes = load_part(name)['shapes']
    pipe_sweeps = [s for s in shapes if s['type'] == 'rings' and s['material'] == 'pipe']
    assert len(pipe_sweeps) >= 2
    assert all(len(s['rings'][0]) == 12 for s in pipe_sweeps)
    # These are genuine complete pipe sections, not a palette or post-render workaround.
    assert all(len(s['rings']) >= 2 for s in pipe_sweeps)


@pytest.mark.parametrize('name', NEW)
@pytest.mark.parametrize('rotation', (0, 90, 180, 270))
def test_new_gantry_four_rotations(name, rotation):
    surfaces, metrics = cast_mesh(_mesh(name), rotation)
    image = surfaces.reference_pixels
    mask = surfaces.material > 0
    assert image.shape == (128, 64) and image.dtype == np.uint8
    assert np.count_nonzero(mask) > 20
    ys, xs = np.nonzero(mask)
    assert ys.min() > 0 and ys.max() < 127
    assert xs.min() > 0 and xs.max() < 63
    assert metrics['visible_primitive_ids'] > 0


@pytest.mark.parametrize('name', ALL)
def test_gantry_can_place_offset_with_existing_loading_annex(name):
    other = 'loading_annex'
    parts = {name: load_part(name), other: load_part(other)}
    assert any(
        packed_scene(parts, (name, other), (turn, 0), axis) is not None
        for axis in (0, 1) for turn in (0, 1, 2, 3)
    ), name


@pytest.mark.parametrize('name,partner', [
    ('gantry_control_gabled', 'gable_shed'),
    ('gantry_stacked_medium', 'storage_tank_small_low_01'),
    ('gantry_compact_quarter_low', 'office_annex'),
    ('gantry_high_long_pipeway', 'enclosed_lift_tower'),
    ('gantry_bridge_enclosed_bay', 'bulk_narrow_charging_tower'),
])
def test_cross_vocabulary_pairs(name, partner):
    parts = {name: load_part(name), partner: load_part(partner)}
    assert any(packed_scene(parts, (name, partner), (0, turn), axis)
               for axis in (0, 1) for turn in (0, 1, 2, 3))


def test_gantry_family_has_both_low_and_high_examples():
    low = [n for n in ALL if max(map(top, load_part(n)['shapes'])) < .42]
    high = [n for n in ALL if n not in low]
    assert len(low) >= 4 and len(high) >= 20


@lru_cache(maxsize=32)
def _mesh(name):
    part = load_part(name)
    return compile_scene({'shapes': rigid_place(part, '', (.5, .5))})
