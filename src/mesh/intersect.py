"""Generic nearest-hit ray/triangle intersection using NumPy alone.

No object, material or lighting special cases; no optional compiled dependencies.
Runs on Python 3.10+ with NumPy. Geometry and camera are supplied separately.
"""
from __future__ import annotations
import numpy as np


def trace(mesh, origins, direction):
    origins=np.asarray(origins,dtype=np.float64)
    ray=np.asarray(direction,dtype=np.float64)
    if origins.ndim!=3 or origins.shape[2]!=3 or ray.shape!=(3,):
        raise ValueError('Expected (H,W,3) origins and (3,) ray')
    shape=origins.shape[:2]
    depth=np.full(shape,np.inf,np.float64)
    normals=np.zeros((*shape,3),np.float64)
    materials=np.zeros(shape,np.uint8)
    components=np.zeros(shape,np.uint16)
    for k,tri in enumerate(mesh.vertices):
        a,b,c=tri
        e1=b-a; e2=c-a
        p=np.cross(ray,e2)
        det=np.dot(e1,p)
        if abs(det)<1e-12:
            continue
        inverse=1/det
        v0=origins-a
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
        hit=possible&(t>1e-8)&(t<depth)
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
        depth[hit]=t[hit]
        normals[hit]=normal[hit]/length[hit,None]
        materials[hit]=mesh.materials[k]
        components[hit]=mesh.component_ids[k]
    return depth,normals,materials,components
