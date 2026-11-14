"""Indexed sprite output and optional diagnostic buffers, independent of geometry."""
from pathlib import Path
import numpy as np
from ..palette import load_palette, save_indexed


def save(surfaces, path, *, buffers=True, display_pixels=None):
    path = Path(path)
    save_indexed(path, surfaces.reference_pixels if display_pixels is None
                 else display_pixels, load_palette())
    if buffers:
        data = dict(material=surfaces.material, normal=surfaces.normal,
                    depth=surfaces.depth, primitive=surfaces.primitive,
                    shaded=surfaces.reference_pixels)
        if surfaces.role is not None:
            data['role'] = surfaces.role
        np.savez_compressed(path.with_suffix('.npz'), **data)
