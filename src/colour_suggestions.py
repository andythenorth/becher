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

from .geometry import MATERIAL_IDS
from .lighting import SUN_FIVE, quantize
from .mesh.camera import rotate_xy
from .mesh.compile import compile_scene
from .mesh.render import cast_mesh
from .palette import load_palette, save_indexed

ROTATIONS = (0, 90, 180, 270)

# Four ordered indices per ramp, all from data/ttd-dos.act. Shared wall/roof
# palettes keep the major buildings uniform; vessels/pipes use independent,
# mostly muted ramps. None of the guides adds surface detail or textures.
STYLES = {
    'brick_slate': {
        'label': 'Brick + slate',
        'wall': (227, 228, 229, 230),
        'roof': (3, 4, 6, 8),
        'tank_wall': (97, 99, 101, 103),
        'pipe': (17, 19, 21, 23),
    },
    'concrete': {
        'label': 'Concrete',
        'wall': (18, 19, 21, 23),
        'roof': (3, 5, 7, 9),
        'tank_wall': (106, 108, 110, 111),
        'pipe': (97, 99, 100, 102),
    },
    'blue_cladding': {
        'label': 'Blue-grey cladding',
        'wall': (154, 155, 156, 158),
        'roof': (3, 4, 6, 8),
        'tank_wall': (16, 18, 20, 22),
        'pipe': (97, 99, 101, 103),
    },
    'cream_green': {
        'label': 'Cream + green roof',
        'wall': (35, 36, 38, 39),
        'roof': (88, 90, 92, 94),
        'tank_wall': (16, 18, 20, 22),
        'pipe': (97, 99, 100, 102),
    },
    'weathered_steel': {
        'label': 'Weathered steel',
        'wall': (104, 106, 109, 111),
        'roof': (3, 5, 7, 9),
        'tank_wall': (16, 18, 20, 22),
        'pipe': (17, 19, 21, 23),
    },
}


def recolour(surfaces, rotation, style):
    """Return 8-bit indexed guide without modifying the source or silhouette.

    The material IDs come directly from each shape in the authored scene.
    No component name matching, vocabulary exclusions or primitive guessing.
    """
    if style not in STYLES:
        raise ValueError(f'Unknown colour suggestion: {style}')
    pixels = surfaces.reference_pixels.copy()
    bands = quantize(surfaces, light=rotate_xy(SUN_FIVE, rotation))
    spec = STYLES[style]
    for material in ('wall', 'roof', 'tank_wall', 'pipe'):
        selected = surfaces.material == MATERIAL_IDS[material]
        pixels[selected] = np.asarray(spec[material], dtype=np.uint8)[bands[selected]]
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
            save_indexed(path, recolour(surfaces, rotation, style), palette)
    result = {'palette': 'data/ttd-dos.act', 'purpose': 'colour reference only',
              'styles': [
                  {'id': name, 'label': spec['label'],
                   'wall': list(spec['wall']), 'roof': list(spec['roof']),
                   'tank_wall': list(spec['tank_wall']), 'pipe': list(spec['pipe']),
                   'angles': list(ROTATIONS)}
                  for name, spec in STYLES.items()]}
    (destination / 'suggestions.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result
