"""Optional artist-oriented material/category recolouring.

This pass preserves the analytic shading bands, but remaps selected visible
classes into stable indexed-palette ranges so adjacent masses and categories are
clearer to the human eye in paint/reference handoff sprites.
"""
from __future__ import annotations
import numpy as np
from .geometry import MATERIAL_IDS, SURFACE_ROLES
from .lighting import quantize
from .foundation_tile import apply as apply_ground_tile

# Main body retains original steel blue. Secondary masses use restrained hues.
HUE_RAMPS = (
    None,
    np.array([82, 83, 84, 85], dtype=np.uint8),
    np.array([136, 137, 139, 141], dtype=np.uint8),
    np.array([102, 103, 104, 105], dtype=np.uint8),
)

# Requested artist-handoff categorical ranges.
WINDOW_RAMP = np.array([130, 131, 133, 135], dtype=np.uint8)
DOOR_RAMP = np.array([171, 173, 175, 177], dtype=np.uint8)
GREEBLE_RAMP = np.array([41, 43, 45, 47], dtype=np.uint8)


def assignment(building, max_hues=3):
    """Stable assembly-to-hue map, shared by all four rotations.

    A hue is allocated to each fabric assembly (not each primitive); smaller
    architectural pieces cycle through the available non-primary hues.
    """
    if max_hues not in (3,4):
        raise ValueError('max_hues must be 3 or 4')
    names=[c.id for c in building.components if c.role=='fabric']
    ordered=sorted(set(names),key=lambda name:(name!='main', names.index(name)))
    return {name:(0 if i==0 else 1+(i-1)%(max_hues-1)) for i,name in enumerate(ordered)}


def _primitive_id_set(primitive_components, *tokens):
    wanted=[]
    low_tokens=tuple(t.lower() for t in tokens)
    for pid,cid in primitive_components.items():
        name=str(cid).lower()
        if any(tok in name for tok in low_tokens):
            wanted.append(int(pid))
    return wanted


def apply(surfaces,primitive_components,building,palette,*,enabled=True,
          max_hues=3,base_pixels=None,contrast_mask=None):
    original=(surfaces.reference_pixels if base_pixels is None else
              np.asarray(base_pixels,dtype=np.uint8))
    out=original.copy()
    assignments=assignment(building,max_hues)
    if not enabled:
        return out, assignments
    bands=quantize(surfaces)
    # When edge contrast was applied earlier, transfer its one-band reduction
    # to the remapped hues instead of painting over the edge in the old colour.
    if contrast_mask is not None:
        m=np.asarray(contrast_mask)!=0
        bands=np.where(m,np.maximum(0,bands.astype(np.int16)-1),bands).astype(np.uint8)

    # 1) Fabric wall masses by attached building volume.
    eligible=((surfaces.material==MATERIAL_IDS['metal']) &
              (surfaces.role==SURFACE_ROLES['wall']))
    for name,hue in assignments.items():
        if not hue:
            continue
        primitive_ids=[int(pid) for pid,cid in primitive_components.items()
                       if cid==name or cid.startswith(name+':roof') or
                          cid.startswith(name+':monitor')]
        if not primitive_ids:
            continue
        where=eligible & np.isin(surfaces.primitive,primitive_ids)
        if np.any(where):
            out[where]=HUE_RAMPS[hue][bands[where]]

    # 2) Doors before windows, since door panels are currently glass solids.
    door_ids=_primitive_id_set(primitive_components,'door','lintel','jamb','header')
    if door_ids:
        door_mask=np.isin(surfaces.primitive,door_ids)
        door_pixels=door_mask & ((surfaces.role==SURFACE_ROLES['glazing']) |
                                 (surfaces.role==SURFACE_ROLES['detail']))
        out[door_pixels]=DOOR_RAMP[bands[door_pixels]]
    else:
        door_pixels=np.zeros_like(out,dtype=bool)

    # Industrial decal doors have distinct frame and panel colours. Generic
    # historical doors keep their original indexed palette for compatibility.
    frame_ids=_primitive_id_set(primitive_components,':frame')
    if frame_ids:
        frame_pixels=door_pixels & np.isin(surfaces.primitive,frame_ids)
        out[frame_pixels]=np.array([17,18,19,20],dtype=np.uint8)[bands[frame_pixels]]
    profile_ids=_primitive_id_set(primitive_components,
                                  '/loading/','/process/','/personnel/')
    if profile_ids:
        industrial=door_pixels & np.isin(surfaces.primitive,profile_ids)
        # Avoid near-white door panels that read as stray window highlights.
        out[industrial & (~np.isin(surfaces.primitive,frame_ids))]=np.array(
            [170,171,172,173],dtype=np.uint8)[bands[industrial & (~np.isin(surfaces.primitive,frame_ids))]]

    # 3) Windows / glazing.
    window_pixels=(surfaces.role==SURFACE_ROLES['glazing']) & (~door_pixels)
    out[window_pixels]=WINDOW_RAMP[bands[window_pixels]]

    # 4) Small detail / greeble accents.
    detail_pixels=(surfaces.role==SURFACE_ROLES['detail']) & (~door_pixels)
    out[detail_pixels]=GREEBLE_RAMP[bands[detail_pixels]]

    # 5) Stable handoff ground tile silhouette.
    out=apply_ground_tile(out,surfaces)
    return out,assignments
