"""Renderer-independent procedural geometry → compiled triangle faces.

Source scenes are plain JSON: list of tagged primitive definitions. The renderer
never sees the primitive descriptions, only the frozen Mesh data.
"""
from __future__ import annotations
import math
import numpy as np
from .solids import Face, _face, box, cylinder


def _sections(path, profiles):
    """Swept closed polygon sections; each ring is explicit world-space xyz.

    The compiler accepts mathematically supplied cross-sections. This is a
    general mesh boundary, not a separate special-case ray intersection.
    """
    if len(path) != len(profiles) or len(path)<2:
        raise ValueError('Need matching cross-sections at two or more stations')
    rings = [np.asarray(r,dtype=float) for r in profiles]
    width=len(rings[0])
    if width<3 or any(r.shape!=(width,3) for r in rings):
        raise ValueError('All sweep sections need identical vertex counts >=3')
    if not all(np.isfinite(r).all() for r in rings):
        raise ValueError('Non-finite sweep')
    return rings


def _cap_triangles(ring):
    """Triangulate a simple planar 3D contour, including concave outlines.

    Ear clipping operates in the contour's own plane. Unlike a triangle fan,
    it never fills recesses outside the polygon. It is independent of rendering.
    """
    # Newell's normal tolerates a concave contour and arbitrary plane orientation.
    next_ring=np.roll(ring,-1,axis=0)
    normal=np.sum(np.cross(ring,next_ring),axis=0)
    magnitude=np.linalg.norm(normal)
    if magnitude<1e-12:
        raise ValueError('Degenerate sweep cap')
    normal/=magnitude
    span=np.ptp(ring,axis=0)
    scale=max(float(np.max(span)),1.)
    if np.max(np.abs((ring-ring[0]) @ normal)) > 1e-7*scale:
        raise ValueError('Sweep end cap must be planar')
    # Drop the axis closest to the face normal; preserves area and is robust
    # for vertical and slanted caps alike.
    coordinates=np.delete(ring,int(np.argmax(np.abs(normal))),axis=1)
    x,y=coordinates[:,0],coordinates[:,1]
    signed_area=float(np.sum(x*np.roll(y,-1)-np.roll(x,-1)*y))
    if abs(signed_area)<1e-12*scale*scale:
        raise ValueError('Degenerate sweep cap area')
    winding=1. if signed_area>0 else -1.
    eps=1e-12*scale*scale

    def orient(a,b,c):
        p,q,r=coordinates[[a,b,c]]
        return float((q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0]))

    # Reject self-intersecting contours explicitly instead of silently
    # emitting a plausible-looking but invalid surface.
    n=len(ring)
    for i in range(n):
        j=(i+1)%n
        for k in range(i+1,n):
            l=(k+1)%n
            if len({i,j,k,l})<4:continue
            o1=orient(i,j,k);o2=orient(i,j,l)
            o3=orient(k,l,i);o4=orient(k,l,j)
            if o1*o2 < -eps*eps and o3*o4 < -eps*eps:
                raise ValueError('Self-intersecting sweep cap')

    pending=list(range(n))
    triangles=[]
    while len(pending)>3:
        ear_found=False
        for pos,b in enumerate(pending):
            a=pending[pos-1];c=pending[(pos+1)%len(pending)]
            if winding*orient(a,b,c)<=eps:continue
            # No other remaining vertex can lie inside this ear, including
            # on its boundary (important at concave and collinear corners).
            if any(winding*orient(a,b,v)>=-eps and
                   winding*orient(b,c,v)>=-eps and
                   winding*orient(c,a,v)>=-eps
                   for v in pending if v not in (a,b,c)):
                continue
            triangles.append((a,b,c))
            pending.pop(pos)
            ear_found=True
            break
        if not ear_found:
            raise ValueError('Sweep cap is not a simple triangulable polygon')
    triangles.append(tuple(pending))
    return triangles,normal


def sweep_rings(rings, material='metal', part='sweep'):
    """Connect matching planar contour rings into a closed polygon shell.

    End caps use general simple-polygon triangulation. Side normals are based
    on contour edges rather than the centroid (which may lie in a recess).
    """
    rings=_sections(rings,rings)
    cap_first,normal_first=_cap_triangles(rings[0])
    cap_last,normal_last=_cap_triangles(rings[-1])
    step=np.mean(rings[-1],axis=0)-np.mean(rings[0],axis=0)
    if np.linalg.norm(step)<1e-9:
        raise ValueError('Sweep rings must advance along a path')
    sign_first=np.dot(normal_first,step)
    sign_last=np.dot(normal_last,step)
    if abs(sign_first)<1e-9 or abs(sign_last)<1e-9 or sign_first*sign_last<0:
        raise ValueError('Sweep rings must have consistent orientation along path')
    winding=1. if sign_first>0 else -1.
    output=[]
    for a,b in zip(rings,rings[1:]):
        advance=np.mean(b,axis=0)-np.mean(a,axis=0)
        if np.linalg.norm(advance)<1e-9:
            raise ValueError('Adjacent sweep rings must be distinct')
        for j in range(len(a)):
            k=(j+1)%len(a)
            edge=((a[k]-a[j])+(b[k]-b[j]))*.5
            outward=np.cross(edge,advance)*winding
            for v in ((a[j],a[k],b[k]),(a[j],b[k],b[j])):
                f=_face(*v,material,part,outward=outward)
                if f is not None:output.append(f)
    # Only two caps; intermediate rings are structural stations, not walls.
    for ring,triangles,outward in ((rings[0],cap_first,-step),
                                   (rings[-1],cap_last,step)):
        for indices in triangles:
            f=_face(*(ring[i] for i in indices),material,part,outward=outward)
            if f is not None:output.append(f)
    return output


def revolution(profile, *, center=(0.5,0.5), segments=32, material='metal', part='vessel'):
    """Revolve (z,r) profile into a closed solid, with interpolated side normals.

    Sphere, cylinder, cone, and hopper all use the same general construction.
    Caps remain planar; poles at radius zero do not generate fake caps.
    """
    values=np.asarray(profile,dtype=float)
    if values.ndim!=2 or values.shape[1] != 2 or len(values)<2 or segments<8:
        raise ValueError('Invalid revolution profile')
    if not np.isfinite(values).all() or np.any(values[:,1]<0) or np.any(np.diff(values[:,0])<=0):
        raise ValueError('Revolution z values must increase; radii must be finite/nonnegative')
    cx,cy=map(float,center)
    out=[]
    z=values[:,0];r=values[:,1]
    slopes=np.gradient(r,z)
    def point(i,j):
        angle=2*math.pi*j/segments
        return np.array((cx+r[i]*math.cos(angle),cy+r[i]*math.sin(angle),z[i]),float)
    def normal(i,j):
        if r[i]<1e-12:
            return np.array((0,0,-1. if i==0 else 1.))
        angle=2*math.pi*j/segments
        n=np.array((math.cos(angle),math.sin(angle),-slopes[i]),float)
        return n/np.linalg.norm(n)
    for i in range(len(z)-1):
        for j in range(segments):
            k=(j+1)%segments
            for ij in (((i,j),(i,k),(i+1,k)),((i,j),(i+1,k),(i+1,j))):
                pts=[point(ii,jj) for ii,jj in ij]
                normals=np.array([normal(ii,jj) for ii,jj in ij])
                outward=normals.mean(axis=0)
                f=_face(*pts,material,part,outward=outward,normals=normals)
                if f is not None:out.append(f)
    # Cap only non-zero-radius endpoints.
    for i,sign in ((0,-1),(len(z)-1,1)):
        if r[i]<=1e-12:continue
        centre=np.array((cx,cy,z[i]))
        for j in range(segments):
            k=(j+1)%segments
            f=_face(centre,point(i,j),point(i,k),material,part,outward=(0,0,sign))
            if f is not None:out.append(f)
    if not out:raise ValueError('Revolution profile produced no triangles')
    return out


def beam_between(start,end,thickness,*,material='frame',part='beam'):
    """Square-section swept beam between arbitrary endpoints (no beam-aware renderer)."""
    a=np.asarray(start,float);b=np.asarray(end,float)
    tangent=b-a
    length=np.linalg.norm(tangent)
    if length<=1e-9 or thickness<=0:raise ValueError('Invalid beam')
    tangent/=length
    hint=np.array([0.,0.,1.]) if abs(tangent[2])<.9 else np.array([0.,1.,0.])
    u=np.cross(tangent,hint);u/=np.linalg.norm(u)
    v=np.cross(tangent,u)
    section=[u+v,u-v,-u-v,-u+v]
    rings=[[ (p+thickness*.5*corner).tolist() for corner in section] for p in (a,b)]
    return sweep_rings(rings,material,part)


def triangle_faces(vertices, *, material='metal', part='mesh', normals=None):
    verts=np.asarray(vertices,dtype=float)
    if verts.ndim!=3 or verts.shape[1:]!=(3,3):raise ValueError('Expected (n,3,3) triangles')
    normals_arr=None if normals is None else np.asarray(normals,float)
    if normals_arr is not None and normals_arr.shape!=verts.shape:raise ValueError('Normal shape differs')
    out=[]
    for i,tri in enumerate(verts):
        n=None if normals_arr is None else normals_arr[i]
        f=_face(*tri,material,part,normals=n)
        if f is not None:out.append(f)
    return out


def scene_faces(scene):
    """Compile arbitrary scenes into triangle faces; no camera/render dependency."""
    out=[]
    for i,shape in enumerate(scene['shapes']):
        kind=shape['type']
        part=shape.get('id',f'part_{i}')
        mat=shape.get('material','metal')
        if kind=='box':out+=box(shape['bounds'],mat,part)
        elif kind=='cylinder':out+=cylinder(shape['bounds'],mat,part)
        elif kind=='beam':out+=beam_between(shape['start'],shape['end'],shape['thickness'],material=mat,part=part)
        elif kind=='revolution':out+=revolution(shape['profile'],center=shape.get('center',(.5,.5)),segments=shape.get('segments',32),material=mat,part=part)
        elif kind=='rings':out+=sweep_rings(shape['rings'],mat,part)
        elif kind=='triangles':out+=triangle_faces(shape['vertices'],material=mat,part=part,normals=shape.get('normals'))
        else:raise ValueError(f'Unknown geometry primitive: {kind}')
    if not out:raise ValueError('No valid triangles in scene')
    return out
