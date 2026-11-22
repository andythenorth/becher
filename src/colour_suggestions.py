"""Optional indexed material studies for authored industrial scenes.

Geometry shapes declare the material they represent. The four ordinary
rendering materials reinterpreted here are building wall, roof, vessel shell,
and pipework; equipment, framing, glass, plinths and chimneys stay as rendered.
The same wall/roof treatment is shared by every major building in a candidate.
This remains a coarse overpainting reference, not finished pixel art.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .lighting import SUN_FIVE, shade
from .mesh.camera import rotate_xy
from .mesh.compile import compile_scene
from .mesh.render import cast_mesh
from .palette import load_palette, save_indexed

ROTATIONS = (0, 90, 180, 270)

# Four ordered indices per ramp, all from data/ttd-dos.act. Shared wall/roof
# palettes keep the major buildings uniform; vessels/pipes use independent,
# mostly muted ramps. Patterns are optional guidance on eligible planes.
STYLES = {
    'brick_slate': {
        'label': 'Brick + slate',
        'wall': (227, 228, 229, 230),
        'roof': (3, 4, 6, 8),
        'tank_wall': (96, 97, 98, 99, 100, 101, 102, 103),
        'pipe': (227, 228, 229, 230),
        'metal_siding': False,
    },
    'concrete': {
        'label': 'Concrete',
        'wall': (18, 19, 21, 23),
        'roof': (3, 5, 7, 9),
        'tank_wall': (104, 105, 106, 107, 108, 109, 110, 111),
        'pipe': (97, 99, 100, 102),
        'metal_siding': False,
    },
    'blue_cladding': {
        'label': 'Blue-grey cladding',
        'wall': (154, 155, 156, 158),
        'roof': (3, 4, 6, 8),
        'tank_wall': (16, 17, 18, 19, 20, 21, 22, 23),
        'pipe': (227, 228, 229, 230),
        'metal_siding': True,
    },
    'cream_green': {
        'label': 'Cream + green roof',
        'wall': (35, 36, 38, 39),
        'roof': (88, 90, 92, 94),
        'tank_wall': (16, 17, 18, 19, 20, 21, 22, 23),
        'pipe': (97, 99, 100, 102),
        'metal_siding': True,
    },
    'weathered_steel': {
        'label': 'Weathered steel',
        'wall': (104, 106, 109, 111),
        'roof': (3, 5, 7, 9),
        'tank_wall': (16, 17, 18, 19, 20, 21, 22, 23),
        'pipe': (227, 228, 229, 230),
        'metal_siding': True,
    },
}

PITCHED_ROOF_MIN_Z = 0.20
PITCHED_ROOF_MAX_Z = 0.965
ROOF_TERMINAL_EPS = 0.020
RIDGE_HEIGHT_EPS = 0.010
MIN_REAR_ROOF_PIXELS = 40  # Avoid dithering exposed one-pixel slivers.
WALL_TEXTURE_STRIDE = 3


def _visible_positions(surfaces, rotation):
    from .mesh.camera import rays
    origins, ray = rays(rotation)
    return origins + surfaces.depth[..., None] * ray


def _pitched_roof_groups(surfaces):
    roof=((surfaces.material==2) & (surfaces.role==2) &
          (surfaces.normal[...,2]>PITCHED_ROOF_MIN_Z) &
          (surfaces.normal[...,2]<PITCHED_ROOF_MAX_Z))
    groups=[]
    if not roof.any():
        return groups
    primitives=np.unique(surfaces.primitive[roof])
    rounded=np.round(surfaces.normal,3)
    for primitive in primitives:
        by_primitive=roof & (surfaces.primitive==primitive)
        normals=np.unique(rounded[by_primitive],axis=0)
        for normal in normals:
            mask=by_primitive & np.all(rounded==normal,axis=-1)
            if mask.any():
                groups.append((int(primitive), normal.astype(np.float64), mask))
    return groups


def _edge_candidate(mask, positions, normal):
    ys, xs = np.nonzero(mask)
    if len(ys) < 8:
        return None
    ridge = np.array([-float(normal[1]), float(normal[0]), 0.0], dtype=np.float64)
    length = np.linalg.norm(ridge)
    if length < 1e-10:
        return None
    ridge /= length
    group_positions = positions[ys, xs]
    along = group_positions @ ridge
    best=None
    for anchor in (along.min(), along.max()):
        terminal = np.abs(along - anchor) < ROOF_TERMINAL_EPS
        ty, tx = ys[terminal], xs[terminal]
        if len(ty) < 6:
            continue
        rows = np.unique(ty)
        per_row = [np.unique(tx[ty==y]) for y in rows]
        if not all(len(values)==1 for values in per_row):
            continue
        cols = np.array([int(values[0]) for values in per_row], dtype=int)
        dy = np.diff(rows)
        dx = np.diff(cols)
        if (len(rows) < 6 or not np.all(dy == 1) or not np.all(dx == dx[0]) or
                abs(int(dx[0])) != 1):
            continue
        score=(len(rows), -np.abs(anchor))
        candidate=(score, rows, cols, int(dx[0]))
        if best is None or candidate[0] > best[0]:
            best=candidate
    return None if best is None else best[1:]


def _one_pixel_roof_perimeter(mask):
    """One indexed pixel on every exposed side of a suitable planar roof.

    The two terminal (gable) edges come from row endpoints and the ridge/eave
    from column endpoints. We paint the union once, including shared corners.
    This uses the *visible* face boundary, not a second ridge overlay.
    """
    border = np.zeros_like(mask, dtype=bool)
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return border
    for y in np.unique(ys):
        row = np.flatnonzero(mask[y])
        border[y, row[0]] = True
        border[y, row[-1]] = True
    for x in np.unique(xs):
        col = np.flatnonzero(mask[:, x])
        border[col[0], x] = True
        border[col[-1], x] = True
    return border



def _rear_roof_two_tone_phase(mask):
    """Return horizontal, one-pixel light/dark courses on a rear roof face.

    Phase is determined *only* by raster Y. Every visible pixel of a row
    receives the same shade; moving along X never shifts or alternates it.
    Thin fragments keep their original shading.
    """
    ys, _ = np.nonzero(mask)
    if len(ys) < MIN_REAR_ROOF_PIXELS:
        return None
    return (ys - int(ys.min())) % 2


def _apply_roof_banding(pixels, surfaces, rotation, roof_ramp):
    """Front: 1:1:1 plus one light perimeter; rear: 1:1 plus ridge.

    The camera-facing roof must have a verified 1-up/1-across raster edge.
    On that face, one perimeter mask covers *all four* edges and includes the
    ridge (there is deliberately no second front-ridge paint operation).
    Narrow or irregular faces fall back to the original material shading.
    """
    from .mesh.camera import rays
    result = np.array(pixels, copy=True)
    positions = _visible_positions(surfaces, rotation)
    _, ray_direction = rays(rotation)
    front_tones = np.asarray((roof_ramp[2], roof_ramp[1], roof_ramp[0]), dtype=np.uint8)
    rear_tones = np.asarray((roof_ramp[2], roof_ramp[1]), dtype=np.uint8)
    ridge_colour = np.uint8(roof_ramp[3])
    touched = np.zeros_like(result, dtype=bool)
    front_outline = np.zeros_like(result, dtype=bool)
    groups = _pitched_roof_groups(surfaces)

    # Paint front planes first so the rear ridge can avoid a double highlight.
    for _, normal, mask in groups:
        facing = -float(np.dot(normal[:2], ray_direction[:2]))
        if facing <= 0.1:
            continue
        edge = _edge_candidate(mask, positions, normal)
        if edge is None:
            continue
        rows, cols, step = edge
        anchor = int(cols[0]) + step * (np.arange(mask.shape[0]) - int(rows[0]))
        ys, xs = np.nonzero(mask)
        phases = (anchor[ys] - xs) % 3
        result[ys, xs] = front_tones[phases]
        border = _one_pixel_roof_perimeter(mask)
        result[border] = ridge_colour
        front_outline |= border
        touched[mask] = True

    for _, normal, mask in groups:
        facing = -float(np.dot(normal[:2], ray_direction[:2]))
        if facing >= -0.1:
            continue
        ys, xs = np.nonzero(mask)
        if len(xs) < MIN_REAR_ROOF_PIXELS:
            continue
        bounds_area = (int(xs.max() - xs.min()) + 1) * (int(ys.max() - ys.min()) + 1)
        if len(xs) / bounds_area < 0.14:
            continue
        phase = _rear_roof_two_tone_phase(mask)
        if phase is None:
            continue
        # Horizontal 1px-wide light/dark courses, constant across each row.
        result[ys, xs] = rear_tones[phase]
        heights = positions[..., 2]
        ridge = mask & (heights >= float(heights[mask].max()) - RIDGE_HEIGHT_EPS)
        # Do not paint a second light pixel immediately beside the front
        # perimeter at the same physical ridge.
        adjacent = front_outline.copy()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            src_y = slice(max(0, -dy), min(mask.shape[0], mask.shape[0]-dy))
            src_x = slice(max(0, -dx), min(mask.shape[1], mask.shape[1]-dx))
            dst_y = slice(max(0, dy), min(mask.shape[0], mask.shape[0]+dy))
            dst_x = slice(max(0, dx), min(mask.shape[1], mask.shape[1]+dx))
            adjacent[dst_y, dst_x] |= front_outline[src_y, src_x]
        result[ridge & ~adjacent] = ridge_colour
        touched[mask] = True
    return result, touched


def _apply_vertical_metal_siding(pixels, surfaces, wall_ramp, *, enabled):
    result = np.array(pixels, copy=True)
    touched = np.zeros_like(result, dtype=bool)
    if not enabled:
        return result, touched
    eligible = ((surfaces.role == 1) &
                np.isin(surfaces.material, np.array([1, 10], dtype=np.uint8)))
    if not eligible.any():
        return result, touched
    inverse = {int(index): band for band, index in enumerate(wall_ramp)}
    for primitive in np.unique(surfaces.primitive[eligible]):
        # Deterministic primitive-level toggle so some wall masses remain plain.
        textured = primitive > 0 and (((int(primitive) * 7) // 3) % 2 == 0)
        if not textured:
            continue
        mask = eligible & (surfaces.primitive == primitive)
        ys, xs = np.nonzero(mask)
        if len(xs) < 16 or np.unique(xs).size < 4:
            continue
        minx = int(xs.min())
        stripe_columns = ((xs - minx) % WALL_TEXTURE_STRIDE) == 0
        stripe = np.zeros_like(mask, dtype=bool)
        stripe[ys[stripe_columns], xs[stripe_columns]] = True
        # Preserve outer silhouette edges; this is internal cladding texture.
        for y in np.unique(ys):
            row_x = np.flatnonzero(mask[y])
            if len(row_x) >= 2:
                stripe[y, row_x[0]] = False
                stripe[y, row_x[-1]] = False
        changed = stripe & mask
        if not changed.any():
            continue
        band = np.vectorize(lambda value: inverse.get(int(value), len(wall_ramp)-1), otypes=[np.int16])(result[changed])
        result[changed] = np.asarray(wall_ramp, dtype=np.uint8)[np.maximum(0, band - 1)]
        touched[changed] = True
    return result, touched


def recolour(surfaces, rotation, style, palette=None):
    """Render material studies through the same shader as the original sprite.

    All geometry, normals, material-specific lighting and non-recoloured
    materials are identical to the regular render; only DOS ramps differ.
    """
    if style not in STYLES:
        raise ValueError(f'Unknown colour suggestion: {style}')
    palette = load_palette() if palette is None else palette
    spec = STYLES[style]
    indices = {material: spec[material]
               for material in ('wall', 'roof', 'tank_wall', 'pipe')}
    pixels = shade(surfaces, palette, light=rotate_xy(SUN_FIVE, rotation),
                   index_ramps=indices)
    roof_pixels, roof_mask = _apply_roof_banding(pixels, surfaces, rotation, spec['roof'])
    pixels = roof_pixels
    wall_pixels, wall_mask = _apply_vertical_metal_siding(
        pixels, surfaces, spec['wall'], enabled=bool(spec.get('metal_siding')))
    pixels = wall_pixels
    if np.any(roof_mask):
        non_roof = roof_mask & (surfaces.material != 2)
        if np.any(non_roof):
            raise ValueError('Roof banding modified non-roof pixels')
    if np.any(wall_mask):
        non_wall = wall_mask & ~((surfaces.role == 1) & np.isin(surfaces.material, np.array([1, 10], dtype=np.uint8)))
        if np.any(non_wall):
            raise ValueError('Wall texturing modified non-wall pixels')
    if not np.array_equal(pixels == 0, surfaces.reference_pixels == 0):
        raise ValueError('Colour suggestion changed silhouette')
    return pixels


def render(scene_file, output):
    """Generate five four-rotation guides using the saved scene and DOS palette."""
    scene_file = Path(scene_file)
    scene = json.loads(scene_file.read_text(encoding='utf-8'))
    mesh = compile_scene(scene)
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=False)
    palette = load_palette()
    for rotation in ROTATIONS:
        surfaces, _ = cast_mesh(mesh, rotation)
        for style in STYLES:
            path = destination / style / f'r{rotation:03d}.png'
            save_indexed(path, recolour(surfaces, rotation, style, palette), palette)
    result = {'palette': 'data/ttd-dos.act', 'purpose': 'colour reference only',
              'styles': [
                  {'id': name, 'label': spec['label'],
                   'wall': list(spec['wall']), 'roof': list(spec['roof']),
                   'tank_wall': list(spec['tank_wall']), 'pipe': list(spec['pipe']),
                   'metal_siding': bool(spec.get('metal_siding')),
                   'angles': list(ROTATIONS)}
                  for name, spec in STYLES.items()]}
    (destination / 'suggestions.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result
