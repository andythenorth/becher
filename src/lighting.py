"""Optional independent normal-based shading pass; no shadows or geometry edits.

The lighting configuration is shared by every active mesh render path.
"""
import numpy as np
import json
from pathlib import Path
from .geometry import MATERIAL_IDS
from .palette import ramp

RAMPS = json.loads((Path(__file__).resolve().parents[1]/"data"/"lighting_ramps.json").read_text())

# High five-o'clock screen-relative key light. The z component must dominate
# so horizontal tops receive more direct light than either vertical wall.
# The mesh renderer rotates this vector with the camera; this is not a
# second normal transform or a per-material correction.
SUN_FIVE = (0.55, 0.30, 1.15)

def _unit_light(light):
    light=np.asarray(light,dtype=np.float64)
    if light.shape!=(3,) or not np.all(np.isfinite(light)):
        raise ValueError('Sun must be three finite components')
    ll=np.linalg.norm(light)
    if ll<1e-10:
        raise ValueError('Light vector must be nonzero')
    return light / ll


def quantize(surfaces, light=SUN_FIVE):
    light = _unit_light(light)
    normal=surfaces.normal.astype(np.float64)
    length=np.linalg.norm(normal,axis=-1,keepdims=True)
    normal=np.divide(normal,length,out=np.zeros_like(normal),where=length>1e-10)
    incident=normal@light
    # Deliberately discrete four-step ramps; geometry and normals are unchanged.
    brightness=np.clip(0.30+0.70*incident,0,1)
    roofs=(surfaces.material==MATERIAL_IDS['roof']) & (normal[...,2]>.08)
    roof_brightness=np.clip(.48+.50*incident+.09*np.maximum(0,normal[...,2]),0,1)
    brightness=np.where(roofs,roof_brightness,brightness)
    bands=np.minimum(3,(brightness*4).astype(np.uint8))
    bands[~surfaces.silhouette]=0
    return bands


def shade(surfaces,palette,light=SUN_FIVE):
    bands=quantize(surfaces,light)
    pixels=np.zeros_like(surfaces.reference_pixels)
    for name,code in MATERIAL_IDS.items():
        sel=surfaces.material==code
        if not np.any(sel):
            continue
        colours = ramp(RAMPS[name],palette)
        if name == 'tank_wall':
            # Use the sun's azimuth so its elevation does not compress the ramp.
            # The default sun is about 16° off the camera's horizontal axis,
            # giving a 106° span from the key to the far visible wall edge.
            horizontal = _unit_light(light)[:2]
            strength = np.linalg.norm(horizontal)
            if strength > 1e-10:
                alignment = np.clip(surfaces.normal[sel, :2] @ (horizontal / strength), -1, 1)
                angle = np.arccos(alignment)
                brightness = np.clip(1 - angle / np.deg2rad(106), 0, 1)
                tank_bands = np.minimum(len(colours) - 1, (brightness * len(colours)).astype(int))
            else:
                tank_bands = len(colours) // 2
            pixels[sel] = colours[tank_bands]
        else:
            pixels[sel] = colours[bands[sel]]
    if not np.array_equal(pixels==0,surfaces.reference_pixels==0):
        raise ValueError('Lighting changed silhouette')
    return pixels

def baseline(surfaces):
    return surfaces.reference_pixels.copy()
