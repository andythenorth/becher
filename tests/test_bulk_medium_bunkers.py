"""Medium bunkers must be drawable and combine with useful industrial neighbours."""

import numpy as np
import pytest

from src.composition import arbitrary_scene, candidates, load_part, vocabularies
from src.geometry import MATERIAL_IDS
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh

MEDIUM = (
    'bulk_rail_bunker_piers_medium',
    'bulk_bunker_buttress_medium',
    'bulk_hopper_house_medium',
    'bulk_coal_tipple_medium',
)


@pytest.mark.parametrize('name', MEDIUM)
def test_medium_bunker_geometry_and_four_angles(name):
    part = load_part(name)
    assert part['role'] == 'structure'
    assert len(part['shapes']) >= 6
    assert len({shape['id'] for shape in part['shapes']}) == len(part['shapes'])
    assert all(shape['material'] in MATERIAL_IDS for shape in part['shapes'])
    x0, y0, x1, y1 = part['footprint']
    assert 0.54 <= x1 - x0 <= 0.65
    assert 0.38 <= y1 - y0 <= 0.45
    mesh = compile_scene(arbitrary_scene([(name, 0.5, 0.5, 0)], {name: part}))
    for angle in (0, 90, 180, 270):
        surface, metrics = cast_mesh(mesh, angle)
        pixels = surface.reference_pixels
        foreground = pixels != 0
        assert np.count_nonzero(foreground) > 100
        assert metrics['visible_primitive_ids'] >= 3
        assert not foreground[0].any() and not foreground[-1].any()
        assert not foreground[:, 0].any() and not foreground[:, -1].any()


def test_medium_bunkers_have_substantial_neighbours():
    vocab = vocabularies()['Bulk loading and bunkers']
    installed = set().union(*map(set, vocab.values()))
    assert set(MEDIUM) <= installed
    pool = candidates(['Bulk loading and bunkers'], 'high')
    # A medium bunker must pair with something other than the small loading annex.
    for name in MEDIUM:
        partners = {
            other
            for scene in pool.values()
            for names in [scene['catalogue']['components']]
            if len(names) >= 2 and name in names
            for other in names if other != name and other != 'loading_annex'
        }
        assert 'bulk_narrow_charging_tower' in partners, name
        assert partners.intersection(set(MEDIUM) - {name}), name


def test_medium_bunkers_compatible_with_dry_handling():
    pool = candidates(['Bulk loading and bunkers', 'Dry material handling'], 'high')
    dry = set().union(*map(set, vocabularies()['Dry material handling'].values()))
    for name in MEDIUM:
        assert any(name in scene['catalogue']['components'] and
                   set(scene['catalogue']['components']) & dry
                   for scene in pool.values()), name
