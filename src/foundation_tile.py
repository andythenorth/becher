"""Fixed artist-handoff ground tile stencil.

This is a 2-D presentation pass applied only to the displayed indexed PNG.
It intentionally replaces the rendered foundation slab silhouette with a
stable diamond tile that artists can paint over consistently.
"""
from __future__ import annotations
from importlib.resources import files
import numpy as np
from PIL import Image
from .geometry import SURFACE_ROLES

GROUND_INDEX = np.uint8(10)


def _mask() -> np.ndarray:
    path = files('becher') / 'data' / 'foundation_tile_mask.png'
    with Image.open(path) as image:
        arr = np.asarray(image)
    # Non-zero pixels define the exact user-supplied tile silhouette.
    return (arr != 0)


def apply(display_pixels, surfaces):
    src = np.asarray(display_pixels, dtype=np.uint8)
    out = src.copy()
    if surfaces.role is None:
        return out
    foundation = surfaces.role == SURFACE_ROLES['foundation']
    if not np.any(foundation):
        return out
    occupied_nonfoundation = (surfaces.material > 0) & (~foundation)
    ys, xs = np.where(foundation)
    bottom = int(ys.max())
    mask = _mask()
    mh, mw = mask.shape
    y0 = bottom - mh + 1
    x0 = 0
    # Clear only the old foundation silhouette; the building itself remains.
    out[foundation] = 0
    tile = np.zeros_like(out, dtype=bool)
    y1 = max(0, y0)
    y2 = min(out.shape[0], y0 + mh)
    x1 = max(0, x0)
    x2 = min(out.shape[1], x0 + mw)
    if y1 >= y2 or x1 >= x2:
        return out
    tile[y1:y2, x1:x2] = mask[y1 - y0:y2 - y0, x1 - x0:x2 - x0]
    paint = tile & (~occupied_nonfoundation)
    out[paint] = GROUND_INDEX
    return out
