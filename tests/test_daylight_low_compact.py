"""Daylight factory variants: correct profiles, useful footprint area and four views."""
import numpy as np
import pytest

from src.composition import (
    HIGH_PROFILE, arbitrary_scene, load_part, packed_scene, top, vocabularies,
)
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh

LOW_RANGE = (
    'daylight_low_office_annex', 'daylight_low_square_shop',
    'daylight_low_wide_mill', 'daylight_low_broad_works',
)
COMPACT = tuple(
    f'daylight_{size}_{profile}_{orientation}'
    for size in ('quarter', 'third')
    for profile in ('low', 'high')
    for orientation in ('x', 'y')
)
ADDED = LOW_RANGE + COMPACT


def test_new_daylight_geometries_are_in_original_vocabulary():
    groups=vocabularies()
    assert set(ADDED) <= set(groups['Daylight factories']['sheds'])
    assert not set(ADDED) & set(groups['Industrial buildings']['sheds'])


@pytest.mark.parametrize('name', ADDED)
def test_daylight_footprints_and_silhouettes(name):
    part=load_part(name)
    assert part['role'] == 'shed'
    assert part.get('placement') != 'tile'
    assert len({s['id'] for s in part['shapes']}) == len(part['shapes'])
    x0,y0,x1,y1=part['footprint']
    assert -.5 < x0 < x1 < .5 and -.5 < y0 < y1 < .5
    area=(x1-x0)*(y1-y0)
    if '_quarter_' in name:
        assert .23 < area < .28
    if '_third_' in name:
        assert .31 < area < .36
    assert (max(map(top,part['shapes'])) < HIGH_PROFILE) == ('_low_' in name)
    bounds=[s['bounds'] for s in part['shapes']]
    assert all(-.5<b[0]<b[3]<.5 and -.5<b[1]<b[4]<.5 for b in bounds)


@pytest.mark.parametrize('name', ADDED)
def test_daylight_variants_render_at_native_scale_in_all_four_rotations(name):
    part=load_part(name)
    scene=arbitrary_scene(((name,.5,.5,0),),{name:part})
    mesh=compile_scene(scene)
    for angle in (0,90,180,270):
        surface, metrics = cast_mesh(mesh, angle)
        fg=surface.reference_pixels!=0
        assert fg.shape == (128,64)
        assert np.count_nonzero(fg)>85
        assert not fg[0].any() and not fg[-1].any()
        assert not fg[:,0].any() and not fg[:,-1].any()
        assert metrics['visible_primitive_ids']>=5


@pytest.mark.parametrize('profile', ('low','high'))
@pytest.mark.parametrize('size', ('quarter','third'))
def test_compact_factory_has_mixed_placement_with_other_vocabulary(profile,size):
    name=f'daylight_{size}_{profile}_x'
    companion='office_annex' if profile=='low' else 'storage_tank_small_high_02'
    parts={n:load_part(n) for n in (name,companion)}
    assert any(packed_scene(parts, (name,companion), (0,0), axis) is not None
               for axis in (0,1))
