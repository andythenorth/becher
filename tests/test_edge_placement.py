"""Regression tests for generic edge-derived placement (no fixed hotspots)."""
from src.composition import packed_scene, packed_sites, arbitrary_scene, candidates
from src.mesh.compile import compile_scene


def block(width, height):
    return {
        'footprint': [-width / 2, -height / 2, width / 2, height / 2],
        'shapes': [{'type': 'box', 'id': 'body', 'material': 'metal',
                    'bounds': [-width / 2, -height / 2, 0,
                               width / 2, height / 2, .2]}],
    }


def test_l_shaped_three_way_arrangement_that_cannot_fit_in_one_row_or_column():
    parts = {'long': block(.65, .36), 'building': block(.25, .29),
             'equipment': block(.25, .29)}
    # .65 + .25 + .25 + 2*.018 > available .93 across X.
    # .36 + .29 + .29 + 2*.018 > available .93 across Y.
    for axis in (0, 1):
        scene = packed_scene(parts, ('long', 'building', 'equipment'), (0, 0, 0), axis)
        assert scene is not None
        assert len(scene['catalogue']['components']) == 3
        assert (compile_scene(scene).vertices[..., :2] <= 1 + 1e-8).all()


def test_lateral_offset_comes_from_dimensions_not_named_locations():
    a = block(.64, .30)
    b = block(.20, .22)
    locations = packed_sites({'first': a, 'second': b}, ('first', 'second'), (0, 0), 0)
    assert locations is not None
    assert locations[0] != locations[1]
    scene = packed_scene({'first': a, 'second': b}, ('first', 'second'), (0, 0), 0)
    assert scene is not None


def test_seeded_candidates_stay_deterministic():
    x = candidates(['Liquid storage'], 'low')
    y = candidates(['Liquid storage'], 'low')
    assert x is y
