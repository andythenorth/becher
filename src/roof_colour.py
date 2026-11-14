"""Optional warm-hue separation for independently attached roof assemblies.

No geometry/visibility changes; only indexed roof-material pixels are remapped.
Deterministic from parent roof component identity, shared across rotations.
"""
from __future__ import annotations
import numpy as np
from .geometry import MATERIAL_IDS
from .lighting import quantize

# Direct DOS palette indices chosen so the brighter front-facing roof bands are
# *also* visibly distinct from the primary yellow ramp.
SECONDARY_ROOF_INDICES = np.array([61, 63, 65, 67], dtype=np.uint8)


def roof_assignments(building):
    fabric=[c.id for c in building.components if c.role=='fabric']
    primary='main' if 'main' in fabric else (fabric[0] if fabric else None)
    roofs=[c for c in building.components if c.role=='roof']
    by_id={c.id:c for c in building.components}
    def owning_fabric(roof):
        parent=roof.parent
        visited=set()
        while parent and parent not in visited:
            visited.add(parent)
            component=by_id.get(parent)
            if component is None:
                break
            if component.role=='fabric':
                return component.id
            parent=component.parent
        return roof.id.split(':roof')[0]
    return {c.id:(0 if owning_fabric(c)==primary else 1) for c in roofs}


def apply(surfaces, primitive_components, building, palette, *, enabled=False,
          base_pixels=None, contrast_mask=None):
    original=(surfaces.reference_pixels if base_pixels is None else
              np.asarray(base_pixels,dtype=np.uint8))
    out=original.copy()
    assignments=roof_assignments(building)
    if not enabled:
        return out,assignments
    bands=quantize(surfaces)
    if contrast_mask is not None:
        m=np.asarray(contrast_mask)!=0
        bands=np.where(m,np.maximum(0,bands.astype(np.int16)-1),bands).astype(np.uint8)
    eligible=(surfaces.material==MATERIAL_IDS['roof'])
    for roof_id,family in assignments.items():
        if family==0:
            continue
        ids=[int(pid) for pid,cid in primitive_components.items()
             if cid==roof_id or cid.startswith(roof_id+':')]
        if ids:
            sel=eligible & np.isin(surfaces.primitive,ids)
            out[sel]=SECONDARY_ROOF_INDICES[bands[sel]]
    if not np.array_equal(out!=0,original!=0):
        raise RuntimeError('Roof hue pass changed the silhouette')
    return out,assignments
