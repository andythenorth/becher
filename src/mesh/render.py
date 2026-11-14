"""Separate pixel treatment: frozen mesh -> depth/normal/material -> indexed image.

No geometry generators or experimental imports.
"""
from __future__ import annotations
from time import perf_counter
import numpy as np
from .compile import compile_building
from .camera import rays, rotate_xy
from .intersect import trace
from ..geometry import VisibleSurfaces, MATERIAL_IDS, SURFACE_ROLES
from ..palette import load_palette
from ..lighting import shade, SUN_FIVE


def cast_mesh(mesh,rotation,*,building=None,facade_mode="boxes"):
    start=perf_counter()
    origins,direction=rays(rotation)
    depth,normal,material,part=trace(mesh,origins,direction)
    role=np.zeros(material.shape,np.uint8)
    role[material>0]=SURFACE_ROLES['wall']
    roof=material==MATERIAL_IDS['roof']
    role[roof & (normal[...,2]>.08)]=SURFACE_ROLES['roof_top']
    role[roof & (np.abs(normal[...,2])<=.08)]=SURFACE_ROLES['roof_fascia']
    role[roof & (normal[...,2]<-.08)]=SURFACE_ROLES['roof_underside']
    role[material==MATERIAL_IDS['glass']]=SURFACE_ROLES['glazing']
    for m in ('frame','chimney','pipe'):
        role[material==MATERIAL_IDS[m]]=SURFACE_ROLES['detail']
    decal_pixels=0
    names={i:name for i,name in enumerate(mesh.component_names,1)}
    if building is not None and facade_mode=='decals':
        # Existing facade pass is a 2D surface-decoration stage, not geometry.
        # Raycast depth/normal/IDs originate exclusively from mesh intersections.
        from ..facade_decals import apply as apply_facade_decals
        origins,direction=rays(rotation)
        ctx={'origin':origins,'ray':direction,'tbest':depth,'normal':normal,'prim':part}
        decal_pixels=apply_facade_decals(ctx,material,role,names,building)
    pixels=np.where(material>0,1,0).astype(np.uint8)
    surf=VisibleSurfaces(material,normal.astype(np.float32),depth.astype(np.float32),part,pixels,role)
    shaded=shade(surf,load_palette(),light=rotate_xy(SUN_FIVE,rotation))
    out=VisibleSurfaces(material,surf.normal,surf.depth,part,shaded,role)
    out.validate()
    count={name:int(np.count_nonzero(part==i)) for i,name in enumerate(mesh.component_names,1) if np.any(part==i)}
    metrics={'occupied_pixels':int(np.count_nonzero(shaded)),
             'visible_primitive_ids':len(count),'total_primitive_ids':len(mesh.component_names),
             'visible_components':count,'primitive_components':{str(i):n for i,n in names.items()},
             'primitive_materials':{},'roof_end_wall_pixels':0,'facade_decal_pixels':decal_pixels,
             'render_ms':round((perf_counter()-start)*1000,3)}
    return out,metrics


def cast(building,rotation,*,facade_mode='boxes'):
    """Public building adapter; compile geometry before any camera operation.

    Mesh path is geometry-first. Legacy facade decaling is not silently applied;
    the optional visual postpass is intentionally separate and is not a solid.
    """
    if facade_mode not in ('boxes','decals'):
        raise ValueError('Unsupported facade mode')
    mesh=compile_building(building,facade_mode=facade_mode)
    return cast_mesh(mesh,rotation,building=building,facade_mode=facade_mode)
