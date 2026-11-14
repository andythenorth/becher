"""One canonical orthographic camera. Geometry, normals and sun never rotate."""
from __future__ import annotations
import numpy as np


def rotate_xy(vector, rotation):
    """Rotate world-space XY vector by the camera's inverse-view angle.

    Keep light and ray transforms in the same coordinate convention.
    """
    if rotation not in (0, 90, 180, 270):
        raise ValueError('Expected quarter-turn rotation')
    v=np.asarray(vector,dtype=np.float64)
    angle=np.deg2rad(-rotation)
    c,s=np.cos(angle),np.sin(angle)
    return np.array([c*v[0]-s*v[1],s*v[0]+c*v[1],v[2]],dtype=np.float64)


def rays(rotation, width=64, height=128):
    """World-space parallel rays for Becher's 2:1 dimetric camera.

    Rotations change camera origins/direction around the tile centre (0.5,0.5).
    No corresponding surface-normal transformation is permitted.
    """
    if rotation not in (0,90,180,270):
        raise ValueError('Expected 0,90,180,270')
    yy,xx=np.mgrid[0:height,0:width].astype(np.float64)
    d=(xx-width*.5)/(width*.5)
    scale=8.0
    ox=np.full_like(d,scale*.5)+d*.5
    oy=np.full_like(d,scale*.5)-d*.5
    oz=(16*scale-(yy-89))*1/36
    direction=np.array([-1.0,-1.0,-32.0/36],dtype=np.float64)
    xy=np.stack((ox-.5,oy-.5),axis=-1)
    angle=np.deg2rad(-rotation)
    c,s=np.cos(angle),np.sin(angle)
    rot=np.array([[c,-s],[s,c]])
    xy=xy @ rot.T
    direction=rotate_xy(direction,rotation)
    origins=np.stack((xy[...,0]+.5,xy[...,1]+.5,oz),axis=-1)
    return origins,direction
