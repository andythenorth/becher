"""Pattern/detail passes for optional colour suggestion guides."""
from __future__ import annotations

import numpy as np
import pytest

from src.colour_suggestions import STYLES, recolour
from src.composition import load_part, rigid_place
from src.geometry import MATERIAL_IDS, SURFACE_ROLES
from src.lighting import SUN_FIVE, shade
from src.mesh.camera import rotate_xy
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh
from src.palette import load_palette


def _base_recolour(surface, rotation, style):
    palette = load_palette()
    spec = STYLES[style]
    return shade(surface, palette, light=rotate_xy(SUN_FIVE, rotation),
                 index_ramps={key: spec[key] for key in ('wall', 'roof', 'tank_wall', 'pipe')})


@pytest.mark.parametrize('rotation', (0, 90, 180, 270))
def test_pitched_roof_guides_gain_pattern_and_ridge(rotation):
    scene = {'shapes': rigid_place(load_part('shed_open_gable_long_broad_high'), '', (.5, .5))}
    surfaces, _ = cast_mesh(compile_scene(scene), rotation)
    before = _base_recolour(surfaces, rotation, 'blue_cladding')
    after = recolour(surfaces, rotation, 'blue_cladding')
    roof = surfaces.material == MATERIAL_IDS['roof']
    changed = roof & (before != after)
    assert changed.any(), rotation
    changed_non_roof = (after != before) & (~roof)
    eligible_wall = ((surfaces.role == SURFACE_ROLES['wall']) &
                     np.isin(surfaces.material, np.array([MATERIAL_IDS['wall'], MATERIAL_IDS['metal']], dtype=np.uint8)))
    assert np.all(changed_non_roof <= eligible_wall)
    assert STYLES['blue_cladding']['roof'][3] in set(int(x) for x in np.unique(after[roof]))
    assert set(int(x) for x in np.unique(after[roof])) <= set(STYLES['blue_cladding']['roof'])


@pytest.mark.parametrize('rotation', (0, 90, 180, 270))
def test_flat_roofs_are_not_patterned(rotation):
    scene = {'shapes': rigid_place(load_part('dispatch_shed'), '', (.5, .5))}
    surfaces, _ = cast_mesh(compile_scene(scene), rotation)
    before = _base_recolour(surfaces, rotation, 'blue_cladding')
    after = recolour(surfaces, rotation, 'blue_cladding')
    roof = surfaces.material == MATERIAL_IDS['roof']
    assert roof.any()
    assert np.array_equal(after[roof], before[roof])


def test_vertical_metal_siding_is_optional_per_wall_primitive():
    scene = {'shapes': [shape for prefix, centre in (('a_', (.30, .42)), ('b_', (.72, .50)))
                        for shape in rigid_place(load_part('enclosed_silo_block'), prefix, centre)]}
    surfaces, _ = cast_mesh(compile_scene(scene), 0)
    before = _base_recolour(surfaces, 0, 'blue_cladding')
    after = recolour(surfaces, 0, 'blue_cladding')
    wall = ((surfaces.role == SURFACE_ROLES['wall']) &
            np.isin(surfaces.material, np.array([MATERIAL_IDS['wall'], MATERIAL_IDS['metal']], dtype=np.uint8)))
    changed = wall & (before != after)
    assert changed.any()
    primitives = [int(p) for p in np.unique(surfaces.primitive[wall]) if p > 0]
    per_primitive = {p: bool(np.any(changed & (surfaces.primitive == p))) for p in primitives}
    assert any(per_primitive.values())
    assert any(not flag for flag in per_primitive.values())
    assert np.array_equal(after[~wall & ~(surfaces.material == MATERIAL_IDS['roof'])],
                          before[~wall & ~(surfaces.material == MATERIAL_IDS['roof'])])


def test_brick_style_does_not_add_metal_siding_texture():
    scene = {'shapes': [shape for prefix, centre in (('a_', (.30, .42)), ('b_', (.72, .50)))
                        for shape in rigid_place(load_part('enclosed_silo_block'), prefix, centre)]}
    surfaces, _ = cast_mesh(compile_scene(scene), 0)
    before = _base_recolour(surfaces, 0, 'brick_slate')
    after = recolour(surfaces, 0, 'brick_slate')
    wall = surfaces.role == SURFACE_ROLES['wall']
    # Roof may change if staircase detection succeeds; walls must not.
    assert np.array_equal(after[wall], before[wall])

@pytest.mark.parametrize('rotation', (0, 90, 180, 270))
@pytest.mark.parametrize('component', ('foundry_monitor_broad', 'shed_open_gable_long_broad_high'))
def test_camera_facing_pitched_roof_has_exactly_one_light_perimeter(component, rotation):
    """The single perimeter mask is also the ridge—never two outlines."""
    from src.colour_suggestions import (
        _pitched_roof_groups, _visible_positions, _edge_candidate,
        _one_pixel_roof_perimeter, _apply_roof_banding,
    )
    from src.mesh.camera import rays
    surface, _ = cast_mesh(compile_scene({
        'shapes': rigid_place(load_part(component), '', (.5, .5))
    }), rotation)
    spec = STYLES['blue_cladding']
    base = _base_recolour(surface, rotation, 'blue_cladding')
    patterned, changed_mask = _apply_roof_banding(base, surface, rotation, spec['roof'])
    positions = _visible_positions(surface, rotation)
    _, ray = rays(rotation)
    selected = 0
    for _, normal, face in _pitched_roof_groups(surface):
        if -float(np.dot(normal[:2], ray[:2])) <= 0.1:
            continue
        if _edge_candidate(face, positions, normal) is None:
            continue
        selected += 1
        outline = _one_pixel_roof_perimeter(face)
        assert np.array_equal(face & (patterned == spec['roof'][3]), outline)
        assert outline.any() and np.all(outline <= face)
        assert np.array_equal(changed_mask[face], np.ones(int(face.sum()), dtype=bool))
        # Verify all four sides: two row extremities and two column extremities.
        for y in np.flatnonzero(face.any(axis=1)):
            xs = np.flatnonzero(face[y])
            assert outline[y, xs[0]] and outline[y, xs[-1]]
        for x in np.flatnonzero(face.any(axis=0)):
            ys = np.flatnonzero(face[:, x])
            assert outline[ys[0], x] and outline[ys[-1], x]
        # The ridge and the roof silhouette are part of this SAME mask.
        # No light colour is present on a second, inner stripe.
        assert not np.any((face & ~outline) & (patterned == spec['roof'][3]))
    assert selected > 0


@pytest.mark.parametrize('rotation', (0, 90, 180, 270))
def test_rear_roof_is_one_to_one_and_shared_ridge_is_not_double_painted(rotation):
    from src.colour_suggestions import (
        _pitched_roof_groups, _visible_positions, _one_pixel_roof_perimeter,
        _edge_candidate, _apply_roof_banding, MIN_REAR_ROOF_PIXELS,
        _rear_roof_two_tone_phase,
    )
    from src.mesh.camera import rays
    surface, _ = cast_mesh(compile_scene({
        'shapes': rigid_place(load_part('shed_open_gable_long_broad_high'), '', (.5, .5))
    }), rotation)
    spec = STYLES['blue_cladding']
    base = _base_recolour(surface, rotation, 'blue_cladding')
    out, _ = _apply_roof_banding(base, surface, rotation, spec['roof'])
    positions = _visible_positions(surface, rotation)
    _, ray = rays(rotation)
    fronts = []
    rears = []
    for _, normal, mask in _pitched_roof_groups(surface):
        facing = -float(np.dot(normal[:2], ray[:2]))
        if facing > 0.1 and _edge_candidate(mask, positions, normal) is not None:
            fronts.append(mask)
        if facing < -0.1 and mask.sum() >= MIN_REAR_ROOF_PIXELS:
            rears.append(mask)
    assert len(fronts) == len(rears) == 1
    front, rear = fronts[0], rears[0]
    assert np.all(out[_one_pixel_roof_perimeter(front)] == spec['roof'][3])
    rear_y, rear_x = np.nonzero(rear)
    # The light ridge can overwrite the upper edge; inspect all other pixels.
    interior = out[rear_y, rear_x] != spec['roof'][3]
    assert interior.any()
    normal = next(n for _, n, m in _pitched_roof_groups(surface) if np.array_equal(m, rear))
    phases = _rear_roof_two_tone_phase(rear)
    expected = np.asarray((spec['roof'][2], spec['roof'][1]), dtype=np.uint8)
    assert np.array_equal(out[rear_y[interior], rear_x[interior]], expected[phases[interior]])
    assert set(np.unique(phases)) == {0, 1}

    # No X or geometry-dependent displacement: every non-ridge pixel at a
    # given Y has exactly the same indexed shade, even on diagonal roof faces.
    tested_rows = 0
    for y in np.unique(rear_y):
        row_x = np.flatnonzero(rear[y] & (out[y] != spec['roof'][3]))
        if len(row_x) < 2:
            continue
        assert np.unique(out[y, row_x]).size == 1
        assert out[y, row_x[0]] == expected[(int(y) - int(rear_y.min())) % 2]
        tested_rows += 1
    assert tested_rows >= 2

    assert np.array_equal(out[~(front | rear)], base[~(front | rear)])


def test_process_pipes_stay_in_approved_brown_red_or_green_ramps():
    brown_red = (227, 228, 229, 230)
    false_green = (97, 99, 100, 102)
    assert {tuple(spec['pipe']) for spec in STYLES.values()} == {brown_red, false_green}
