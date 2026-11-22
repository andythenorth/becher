"""The standalone charging tower must include its own ground-reaching chute."""

import numpy as np

from src.composition import arbitrary_scene, load_part
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh


def test_charging_tower_chute_reaches_ground_and_renders_at_all_angles():
    part = load_part('bulk_narrow_charging_tower')
    chute = next(s for s in part['shapes'] if s['id'] == 'drop_spout')
    tower = next(s for s in part['shapes'] if s['id'] == 'charging_tower')
    assert chute['type'] == 'beam'
    # A free-standing component must not rely on a neighbouring loading annex.
    assert chute['end'][2] - chute['thickness'] / 2 <= 0.01
    assert chute['end'][0] > tower['bounds'][3] + 0.15
    assert chute['end'][0] + chute['thickness'] / 2 <= part['footprint'][2]
    scene = arbitrary_scene([('bulk_narrow_charging_tower', .5, .5, 0)],
                            {'bulk_narrow_charging_tower': part})
    mesh = compile_scene(scene)
    for angle in (0, 90, 180, 270):
        surface, _ = cast_mesh(mesh, angle)
        pixels = surface.reference_pixels
        assert pixels.shape == (128, 64)
        assert np.count_nonzero(pixels) > 100
        assert not pixels[0].any() and not pixels[-1].any()
        assert not pixels[:, 0].any() and not pixels[:, -1].any()
