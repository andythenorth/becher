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


def quantize(surfaces, light=SUN_FIVE, steps=4):
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
    bands=np.minimum(steps-1,(brightness*steps).astype(np.uint8))
    bands[~surfaces.silhouette]=0
    return bands


def shade(surfaces, palette, light=SUN_FIVE, *, index_ramps=None):
    """Apply normal material lighting, optionally substituting DOS index ramps.

    A recolour changes the palette indices, not the material-specific lighting
    calculation. Each replacement ramp must have the same number of shades as
    the ordinary material ramp (eight for tank_wall, four for wall/roof/pipe).
    """
    index_ramps = {} if index_ramps is None else index_ramps
    for name, indices in index_ramps.items():
        if name not in RAMPS or len(indices) != len(RAMPS[name]):
            raise ValueError(f'Invalid indexed ramp for material {name}')
        if any(not isinstance(i, (int, np.integer)) or not 1 <= i <= 255 for i in indices):
            raise ValueError(f'Invalid DOS palette indices for {name}')
    bands=quantize(surfaces,light)
    pixels=np.zeros_like(surfaces.reference_pixels)
    for name,code in MATERIAL_IDS.items():
        sel=surfaces.material==code
        if not np.any(sel):
            continue
        colours = (np.asarray(index_ramps[name], dtype=np.uint8)
                   if name in index_ramps else ramp(RAMPS[name], palette))
        if name == 'tank_wall':
            # Vertical cylinder walls need an azimuth ramp, but top faces and
            # shoulders must use their actual surface normals. Treating all
            # tank normals as horizontal makes lids dark and sides dome-like.
            selected_normals = surfaces.normal[sel]
            # Cap top/shoulder highlights below the brightest wall stripe.
            cap_bands = np.minimum(quantize(surfaces, light, len(colours))[sel], len(colours) - 3)
            output = colours[cap_bands]
            sides = np.abs(selected_normals[:, 2]) < 0.18
            horizontal = _unit_light(light)[:2]
            strength = np.linalg.norm(horizontal)
            if strength > 1e-10 and np.any(sides):
                alignment = np.clip(selected_normals[sides, :2] @ (horizontal / strength), -1, 1)
                angle = np.arccos(alignment)
                brightness = np.clip(1 - angle / np.deg2rad(90), 0, 1)
                side_bands = np.minimum(len(colours) - 1, (brightness * len(colours)).astype(int))
                output[sides] = colours[side_bands]
            pixels[sel] = output
        elif name == 'chimney':
            # Round vertical surfaces need their own azimuth ramp: the high
            # key-light elevation otherwise compresses most visible sides into
            # the same two or three bands. Keep caps on the normal-based ramp.
            horizontal = _unit_light(light)[:2]
            strength = np.linalg.norm(horizontal)
            side = np.abs(surfaces.normal[sel, 2]) < .90
            selected_normals = surfaces.normal[sel]
            output = colours[np.minimum(len(colours)-1,
                (bands[sel].astype(np.float64) * (len(colours)-1) / 3).astype(int))]
            if strength > 1e-10 and np.any(side):
                alignment = np.clip(selected_normals[side, :2] @ (horizontal / strength), -1, 1)
                angle = np.arccos(alignment)
                brightness = np.clip(1 - angle / np.deg2rad(165), 0, 1)
                side_bands = np.minimum(len(colours) - 1,
                    (brightness * len(colours)).astype(int))
                output[side] = colours[side_bands]
            pixels[sel] = output
        elif name == 'equipment':
            pixels[sel] = colours[quantize(surfaces, light, len(colours))[sel]]
        else:
            pixels[sel] = colours[bands[sel]]
    if not np.array_equal(pixels==0,surfaces.reference_pixels==0):
        raise ValueError('Lighting changed silhouette')
    return pixels

def baseline(surfaces):
    return surfaces.reference_pixels.copy()
