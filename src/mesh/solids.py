"""Compile geometric solids to triangles. No camera, pixel, light or renderer imports.

All positions are in canonical world coordinates. Winding is outward; smooth
normals are assigned only to curved side walls, not to caps or polygon corners.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class Face:
    xyz: np.ndarray           # (3,3) world-space vertices
    normals: np.ndarray       # (3,3) world-space vertex normals
    material: str
    part: str


def _face(a, b, c, material, part, outward=None, normals=None):
    v = np.array([a, b, c], dtype=np.float64)
    n = np.cross(v[1] - v[0], v[2] - v[0])
    length = np.linalg.norm(n)
    if length < 1e-12:
        return None
    n = n / length
    if outward is not None and np.dot(n, outward) < 0:
        v = v[[0, 2, 1]]
        n = -n
        if normals is not None:
            normals = np.asarray(normals)[[0, 2, 1]]
    ns = np.broadcast_to(n, (3, 3)).copy() if normals is None else np.array(normals, dtype=np.float64)
    v.setflags(write=False)
    ns.setflags(write=False)
    return Face(v, ns, material, part)


def _closed_polyhedron(polygons, material, part, material_for_face=None):
    """Polygon soup from a convex closed shape; outward normals via interior point.

    Faces are intentionally independent: no CSG or watertightness inference.
    """
    center = np.mean(np.array([v for p in polygons for v in p], float), axis=0)
    out = []
    for face_i, polygon in enumerate(polygons):
        ctr = np.mean(polygon, axis=0)
        mat = material_for_face(face_i, polygon) if material_for_face else material
        for j in range(1, len(polygon)-1):
            tri = _face(polygon[0], polygon[j], polygon[j+1], mat, part, outward=np.asarray(ctr)-center)
            if tri is not None:
                out.append(tri)
    return out


def box(bounds, material, part):
    x0,y0,z0,x1,y1,z1 = bounds
    if not (x1>x0 and y1>y0 and z1>z0):
        return []
    p=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
       (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    polys=[[p[i] for i in face] for face in
           [(0,1,2,3),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]]
    return _closed_polyhedron(polys,material,part)


def prism(section, axis, minimum, maximum, material, part, end_material=None):
    """Extrude an ordered (horizontal coordinate,Z) section along X or Y."""
    if maximum<=minimum or len(section)<3:
        raise ValueError('Invalid prism section')
    if axis=='x':
        start=[(minimum,h,z) for h,z in section]
        end=[(maximum,h,z) for h,z in section]
    elif axis=='y':
        start=[(h,minimum,z) for h,z in section]
        end=[(h,maximum,z) for h,z in section]
    else:
        raise ValueError('prism axis must be x or y')
    polys=[list(reversed(start)),end]
    for i in range(len(start)):
        j=(i+1)%len(start)
        polys.append([start[i],start[j],end[j],end[i]])
    # end material for vertical terminal faces, roof material elsewhere
    def mat(i,polygon):
        if end_material and i in (0,1):
            return end_material
        if end_material and i>=2 and abs(polygon[0][2]-polygon[1][2])>1e-8:
            # gable elevation ends are handled by i=0,1; slopes retain roof
            pass
        return material
    return _closed_polyhedron(polys, material, part, mat)


def cylinder(bounds, material, part, segments=32):
    x0,y0,z0,x1,y1,z1=bounds
    cx=(x0+x1)*.5; cy=(y0+y1)*.5
    rx=(x1-x0)*.5; ry=(y1-y0)*.5
    if min(rx,ry,z1-z0)<=0:
        return []
    rings=[]
    for z in (z0,z1):
        rings.append([(cx+rx*math.cos(i*2*math.pi/segments),
                       cy+ry*math.sin(i*2*math.pi/segments),z) for i in range(segments)])
    out=[]
    for i in range(segments):
        j=(i+1)%segments
        bottom,top=rings
        radial=[]
        for p in (bottom[i],bottom[j],top[j],top[i]):
            nx=(p[0]-cx)/(rx*rx);ny=(p[1]-cy)/(ry*ry)
            radial.append(np.array((nx,ny,0),float)/math.hypot(nx,ny))
        for ii in ((0,1,2),(0,2,3)):
            ps=[(bottom[i],bottom[j],top[j],top[i])[k] for k in ii]
            normals=[radial[k] for k in ii]
            out.append(_face(*ps,material,part,outward=(sum(q[0] for q in ps)/3-cx,sum(q[1] for q in ps)/3-cy,0),normals=normals))
        out.append(_face((cx,cy,z0),bottom[j],bottom[i],material,part,outward=(0,0,-1)))
        out.append(_face((cx,cy,z1),top[i],top[j],material,part,outward=(0,0,1)))
    return [face for face in out if face is not None]


def roof(component, wall_material):
    x0,y0,z0,x1,y1,z=component.bounds
    e=.009; x0-=e;x1+=e;y0-=e;y1+=e
    bottom=z-.016
    kind=component.roof
    if kind=='flat':
        return box((x0,y0,bottom,x1,y1,z+.027),'roof',component.id)
    if kind in ('gable_x','monitor','gable_y'):
        axis='x' if kind in ('gable_x','monitor') else 'y'
        lo,hi=(y0,y1) if axis=='x' else (x0,x1)
        section=[(lo,bottom),(hi,bottom),(hi,z),((lo+hi)*.5,z+component.rise),(lo,z)]
        return prism(section,axis,x0 if axis=='x' else y0,x1 if axis=='x' else y1,
                     'roof',component.id,wall_material)
    if kind=='shed':
        section=[(y0,bottom),(y1,bottom),(y1,z),(y0,z+component.rise)]
        return prism(section,'x',x0,x1,'roof',component.id,wall_material)
    if kind=='sawtooth':
        count=max(2,component.count)
        thickness=min(.025,component.rise*.18)
        out=[]
        for i in range(count):
            lo=y0+(y1-y0)*i/count;hi=y0+(y1-y0)*(i+1)/count
            section=[(lo,z+component.rise-thickness),(hi,z-thickness),
                     (hi,z),(lo,z+component.rise)]
            out+=prism(section,'x',x0,x1,'roof',f'{component.id}:sheet:{i}')
            glazing_bottom=z+.014
            glazing_top=z+component.rise-thickness*.70
            if glazing_top>glazing_bottom:
                yy=lo-.014
                out+=box((x0+.022,yy,glazing_bottom,x1-.022,lo+.003,glazing_top),
                         'glass',f'{component.id}:clerestory:{i}')
                for k in range(1,4):
                    xx=x0+(x1-x0)*k/4
                    out+=box((xx-.006,yy-.002,glazing_bottom,xx+.006,lo+.005,glazing_top),
                             'frame',f'{component.id}:mullion:{i}:{k}')
                out+=box((x0+.018,yy-.005,glazing_top-.006,x1-.018,lo+.005,glazing_top+.008),
                         'frame',f'{component.id}:lintel:{i}')
        return out
    raise ValueError(f'Unsupported roof: {kind}')
