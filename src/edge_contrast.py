"""Palette-faithful, one-pixel *inward* architectural edge contrast.

Strictly post-processes the 1x visible G-buffer: no geometry, texture,
ray intersection, silhouette, material, primitive ID or depth modifications.
Nothing is drawn outside the original raster footprint.

The optional mask is independent, which allows artist review / paint-over.
"""
from __future__ import annotations
import numpy as np
from .geometry import MATERIAL_IDS, SURFACE_ROLES
from .lighting import RAMPS, quantize
from .palette import ramp


def visible_roles(surfaces):
    """Compatibility inference for saved NPZs made before surface roles existed."""
    if surfaces.role is not None:
        return surfaces.role
    m=surfaces.material
    r=np.zeros(m.shape,dtype=np.uint8)
    r[m!=0]=SURFACE_ROLES['wall']
    r[m==MATERIAL_IDS['roof']]=SURFACE_ROLES['roof_fascia']
    r[(m==MATERIAL_IDS['roof']) & (surfaces.normal[...,2]>.08)]=SURFACE_ROLES['roof_top']
    r[(m==MATERIAL_IDS['roof']) & (surfaces.normal[...,2]<-.08)]=SURFACE_ROLES['roof_underside']
    r[m==MATERIAL_IDS['glass']]=SURFACE_ROLES['glazing']
    for name in ('frame','pipe','chimney'):
        r[m==MATERIAL_IDS[name]]=SURFACE_ROLES['detail']
    return r


def edge_mask(surfaces):
    """Compute 4-connected pixel-space exposed-edge and ridge mask.

Only roof upper faces and substantial wall corner faces are eligible.
Fine windows/pipes/greeble and roof undersides are never darkened,
regardless of primitive overlap. No colour comparison is involved.
"""
    roles=visible_roles(surfaces)
    mat=surfaces.material
    sheet=roles==SURFACE_ROLES['sawtooth_sheet']
    roof=(roles==SURFACE_ROLES['roof_top']) | sheet
    wall=roles==SURFACE_ROLES['wall']
    structural=roof | wall
    normals=surfaces.normal
    # A mask is marked only on the *interior* side of a detected boundary.
    found=np.zeros(mat.shape,dtype=bool)
    for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
        # Physical source and neighbour slices, with no wrap-around.
        ys=slice(max(0,-dy),min(mat.shape[0],mat.shape[0]-dy))
        xs=slice(max(0,-dx),min(mat.shape[1],mat.shape[1]-dx))
        yn=slice(max(0,dy),min(mat.shape[0],mat.shape[0]+dy))
        xn=slice(max(0,dx),min(mat.shape[1],mat.shape[1]+dx))
        ar=roof[ys,xs]; aw=wall[ys,xs]
        nr=roof[yn,xn]; nw=wall[yn,xn]
        nm=normals[ys,xs];nn=normals[yn,xn]
        dot=np.einsum('ijk,ijk->ij',nm,nn)
        # 1. Don't darken a roof simply because it meets transparent
        #    blue sky: roof/sky is already a very high-contrast boundary.
        #    Outlining this creates brown speckling on 1x gable peaks.
        silhouette=np.zeros(ar.shape,dtype=bool)
        # 2. Roof-to-wall eaves, and the edge between a sloping
        #    sheet and its vertical fascia. Keep the line on the roof.
        eaves=ar & (nw | (roles[yn,xn]==SURFACE_ROLES['roof_fascia']))
        # 3. Roof-to-roof ridge / sawtooth joint (normal discontinuity).
        # One face gets the contrast line, not a 2px band on both sides.
        ridge=sheet[ys,xs] & sheet[yn,xn] & (dot<.93) & (np.maximum(np.abs(nm[...,0]),np.abs(nm[...,1]))
                                           <= np.maximum(np.abs(nn[...,0]),np.abs(nn[...,1])))
        # 4. External building wall corners only. Exclude windows and
        # structural greebles by role (not arbitrary primitive ID changes).
        wall_corner=aw & nw & (dot<.57) & (nm[...,0]+nm[...,1] >= nn[...,0]+nn[...,1])
        found[ys,xs] |= silhouette | eaves | ridge | wall_corner
    return found & structural


def apply(surfaces,palette,*,enabled=True,base_pixels=None):
    """Return (indexed pixels, independent 0/255 mask). Defaults to OFF upstream.

All output palette indices come from the *same per-material DOS ramps* as
normal shading. Pixel geometry and transparency never change.
    """
    original=(surfaces.reference_pixels if base_pixels is None else
              np.asarray(base_pixels,dtype=np.uint8))
    if original.shape != (128,64):
        raise ValueError('Input indexed sprite must be 128x64 pixels')
    if not np.array_equal(original!=0,surfaces.silhouette):
        raise ValueError('Edge pass refuses different source silhouette')
    if not enabled:
        return original.copy(),np.zeros(original.shape,dtype=np.uint8)
    selected=edge_mask(surfaces)
    bands=quantize(surfaces)
    out=original.copy()
    actual=np.zeros(original.shape,dtype=np.uint8)
    for name in ('roof','metal','concrete'):
        # The low two roof steps are already dark. Darkening those at
        # 1x often closes narrow sawtooth gaps and creates brown blobs.
        minimum=2 if name=='roof' else 1
        where=selected & (surfaces.material==MATERIAL_IDS[name]) & (bands>=minimum)
        if not np.any(where):
            continue
        colours=ramp(RAMPS[name],palette)
        new=colours[bands[where]-1]
        changed=new!=out[where]
        out[where]=new
        # The displayed mask flags only pixels that genuinely changed.
        actual[where]=np.where(changed,255,0).astype(np.uint8)
    if not np.array_equal(out!=0,original!=0):
        raise RuntimeError('Edge shader changed the silhouette')
    return out,actual
