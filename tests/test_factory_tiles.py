"""Factory sections are ordinary single-tile Becher assembly geometries."""
import numpy as np
import pytest

from src.composition import (
    arbitrary_scene, component_catalogue, load_part, vocabularies,
)
from src.geometry import MATERIAL_IDS
from src.mesh.compile import compile_scene
from src.mesh.camera import rays
from src.mesh.intersect import trace

FACTORY_TILES = (
    'factory_tile_corner_e',
    'factory_tile_corner_e_foundry',
    'factory_tile_corner_e_low',
    'factory_tile_end_e',
    'factory_tile_end_e_stack',
    'factory_tile_end_w',
    'factory_tile_end_w_stack',
    'factory_tile_junction_t',
    'factory_tile_junction_t_tall',
    'factory_tile_mid',
    'factory_tile_mid_2stacks',
    'factory_tile_wing_end_corner',
    'factory_tile_wing_end_corner_foundry',
    'factory_tile_wing_end_corner_low',
    'factory_tile_wing_end_t',
    'factory_tile_wing_end_t_tall',
    'factory_tile_wing_mid_t',
)

DAYLIGHT_STANDALONE = (
    'daylight_long_columnated', 'daylight_tall_five_storey',
    'daylight_end_stair_tower', 'dagenham_pair_chimneys',
    'dagenham_four_chimneys', 'dagenham_stepped_three_stacks',
    'foundry_heavy_daylight', 'powerhouse_high_window',
)


def test_daylight_factory_vocabulary_separates_tile_sections_and_regular_buildings():
    catalogue = component_catalogue()
    groups = vocabularies()
    assert 'General industrial' not in groups
    assert set(FACTORY_TILES + DAYLIGHT_STANDALONE) == set(groups['Daylight factories']['sheds'])
    assert not set(FACTORY_TILES + DAYLIGHT_STANDALONE) & set(groups['Industrial buildings']['sheds'])
    assert {'mill_steel_gable_long', 'mill_clerestory_tall'} <= set(groups['Industrial buildings']['sheds'])
    assert set(FACTORY_TILES + DAYLIGHT_STANDALONE) <= set(catalogue)


@pytest.mark.parametrize('name', DAYLIGHT_STANDALONE)
def test_standalone_daylight_factory_uses_actual_footprint(name):
    part = load_part(name)
    assert part.get('placement') != 'tile'
    x0,y0,x1,y1 = part['footprint']
    assert 0 < x1-x0 < .93 and 0 < y1-y0 < .93


@pytest.mark.parametrize('name', FACTORY_TILES)
def test_factory_section_is_regular_single_tile_geometry(name):
    part = load_part(name)
    assert part['placement'] == 'tile'
    assert part['role'] == 'structure'
    assert len(part['footprint']) == 4
    assert part['shapes']
    assert len({s['id'] for s in part['shapes']}) == len(part['shapes'])
    assert all(s['material'] in MATERIAL_IDS for s in part['shapes'])
    for s in part['shapes']:
        assert s['type'] in ('box', 'cylinder')
        b=s['bounds']
        assert all(b[i] < b[i+3] for i in range(3))
        assert all(-.5-1e-6 <= b[i] <= b[i+3] <= .5+1e-6 for i in (0,1))
    area = part['footprint']
    assert (max(area[2]-area[0], area[3]-area[1]) >= 1-1e-6)
    scene = arbitrary_scene(((name, .5, .5, 0),), {name:part})
    assert scene['catalogue']['components'] == [name]
    assert scene['catalogue']['type'] == '1-component'
    mesh = compile_scene(scene)
    assert len(mesh.vertices) > 0
    assert np.isfinite(mesh.vertices).all()

@pytest.mark.parametrize('name', FACTORY_TILES)
@pytest.mark.parametrize('angle', (0, 90, 180, 270))
def test_factory_sections_render_through_normal_camera(name, angle):
    part = load_part(name)
    scene = arbitrary_scene(((name, .5, .5, 0),), {name:part})
    mesh = compile_scene(scene)
    origin,direction = rays(angle)
    depth,normal,materials,components = trace(mesh,origin,direction,affine_grid=True)
    assert materials.shape == (128,64)
    assert np.count_nonzero(materials) > 80
    ys,xs = np.nonzero(materials)
    # The native 64px camera can crop side edges of full-width corner
    # sections; those edges continue onto neighbouring tile sprites.
    # Verify that the vertical image extent remains within frame.
    assert ys.min()>0 and ys.max()<127

@pytest.mark.parametrize('other', ('Industrial buildings', 'Liquid storage',
                                    'Chimneys', 'Bulk loading and bunkers'))
def test_daylight_non_tile_buildings_mix_with_other_vocabulary(other):
    from src.composition import candidates
    groups = vocabularies()
    others = {n for names in groups[other].values() for n in names}
    pool = candidates(['Daylight factories', other], 'high')
    assert any(len(scene['catalogue']['components']) > 1
               and set(scene['catalogue']['components']) & set(DAYLIGHT_STANDALONE)
               and set(scene['catalogue']['components']) & others
               for scene in pool.values()), other


def test_full_width_factory_sections_remain_single_tile_only():
    from src.composition import packed_scene
    name = 'factory_tile_mid'
    other = 'loading_annex'
    parts = {n: load_part(n) for n in (name, other)}
    for axis in (0, 1):
        assert packed_scene(parts, (name, other), (0, 0), axis) is None
