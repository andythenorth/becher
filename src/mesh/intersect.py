"""Generic nearest-hit ray/triangle intersection using NumPy alone.

No object, material or lighting special cases; no optional compiled dependencies.
Runs on Python 3.10+ with NumPy. Geometry and camera are supplied separately.
"""
from __future__ import annotations
import numpy as np


def _pixel_bounds(vertices, origins, ray):
    """Conservative triangle bounds on the affine parallel-ray grid."""
    origin = origins[0, 0]
    basis = np.column_stack((origins[0, 1]-origin, origins[1, 0]-origin, ray))
    try:
        projection = np.linalg.inv(basis)[:2]
    except np.linalg.LinAlgError:
        return None
    projected = (vertices-origin) @ projection.T
    lower = projected.min(axis=1)
    upper = projected.max(axis=1)
    # Include the intersection test's barycentric tolerance at the edges.
    padding = 1 + 4e-9*(upper-lower)
    limits = origins.shape[1::-1]
    start = np.clip(np.floor(lower-padding), 0, limits).astype(int)
    stop = np.clip(np.ceil(upper+padding)+1, 0, limits).astype(int)
    return np.column_stack((start,stop))


def trace(mesh, origins, direction, *, affine_grid=False):
    """Intersect parallel rays. The camera can supply an affine pixel grid."""
    origins=np.asarray(origins,dtype=np.float64)
    ray=np.asarray(direction,dtype=np.float64)
    if origins.ndim!=3 or origins.shape[2]!=3 or ray.shape!=(3,):
        raise ValueError('Expected (H,W,3) origins and (3,) ray')
    shape=origins.shape[:2]
    depth=np.full(shape,np.inf,np.float64)
    normals=np.zeros((*shape,3),np.float64)
    materials=np.zeros(shape,np.uint8)
    components=np.zeros(shape,np.uint16)
    bounds = _pixel_bounds(mesh.vertices, origins, ray) if affine_grid and min(shape)>1 else None
    for k,tri in enumerate(mesh.vertices):
        if bounds is None:
            region = np.s_[:, :]
        else:
            x0,y0,x1,y1 = bounds[k]
            if x0 >= x1 or y0 >= y1:
                continue
            region = np.s_[y0:y1, x0:x1]
        local_depth = depth[region]
        a,b,c=tri
        e1=b-a; e2=c-a
        p=np.cross(ray,e2)
        det=np.dot(e1,p)
        if abs(det)<1e-12:
            continue
        inverse=1/det
        v0=origins[region]-a
        u=(v0@p)*inverse
        possible=(u>=-1e-9)&(u<=1+1e-9)
        if not np.any(possible):
            continue
        q=np.cross(v0,e1)
        v=(q@ray)*inverse
        possible &= (v>=-1e-9)&(u+v<=1+1e-9)
        if not np.any(possible):
            continue
        t=(q@e2)*inverse
        hit=possible&(t>1e-8)&(t<local_depth)
        if not np.any(hit):
            continue
        w=1-u-v
        normal=(w[...,None]*mesh.normals[k,0]+
                u[...,None]*mesh.normals[k,1]+
                v[...,None]*mesh.normals[k,2])
        length=np.linalg.norm(normal,axis=-1)
        hit &= length>1e-12
        if not np.any(hit):
            continue
        local_depth[hit]=t[hit]
        normals[region][hit]=normal[hit]/length[hit,None]
        materials[region][hit]=mesh.materials[k]
        components[region][hit]=mesh.component_ids[k]
    return depth,normals,materials,components
