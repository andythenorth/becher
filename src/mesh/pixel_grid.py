"""Pixel-grid alignment shared by vertically radial mesh primitives."""
from __future__ import annotations

import math


def radial_center(center):
    """Snap a vertical radial axis to Becher's four-view pixel lattice.

    The canonical 64px ray grid advances by 1/64 world unit along X or Y.
    Quantizing both centre coordinates to that pitch makes x-y and x+y
    projections land on pixel-centre or pixel-boundary axes in every quarter
    turn. The maximum translation is 1/128 world unit per coordinate; radii,
    profiles and authored scene coordinates are unchanged.
    """
    return tuple(math.floor(float(value) * 64.0 + 0.5) / 64.0 for value in center)
