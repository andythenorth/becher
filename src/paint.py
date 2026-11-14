"""Artist-authored indexed overlay; zero means preserve the underlying pixel."""
from .palette import save_indexed,open_indexed
import numpy as np


def make_blank(path,palette):
    return save_indexed(path,np.zeros((128,64),dtype=np.uint8),palette)


def apply(surfaces,parent,overlay_path,palette,allow_materials=None):
    overlay=open_indexed(overlay_path,palette)
    base=np.asarray(parent)
    painted=overlay!=0
    if np.any(painted & ~surfaces.silhouette):
        raise ValueError('Artist layer paints outside visible geometry')
    if allow_materials:
        allowed=np.isin(surfaces.material,allow_materials)
        if np.any(painted & ~allowed):
            raise ValueError('Artist layer paints outside allowed materials')
    out=np.array(base,copy=True)
    out[painted]=overlay[painted]
    return out


def apply_rgba(surfaces, parent, rgba_path, palette, *, exact=False):
    """Import a human-painted transparent PNG; preserve geometry and DOS palette.

    Only alpha=0 (untouched) and alpha=255 (one full-resolution pixel) are
    permitted. Partial opacity is rejected rather than silently antialiased.
    """
    from PIL import Image
    with Image.open(rgba_path) as image:
        if image.size != (64,128) or image.mode != 'RGBA':
            raise ValueError('Artist overlay must be a 64x128 RGBA PNG')
        rgba=np.asarray(image).copy()
    painted = rgba[...,3] != 0
    if np.any((rgba[...,3]!=0) & (rgba[...,3]!=255)):
        raise ValueError('Antialiased/partial alpha is not permitted for 1x pixel art')
    if np.any(painted & ~surfaces.silhouette):
        raise ValueError('Artist overlay contains paint outside the sprite silhouette')
    if not np.array_equal(np.asarray(parent)!=0, surfaces.silhouette):
        raise ValueError('Source image does not match saved geometry')
    result=np.asarray(parent).copy()
    if not painted.any():
        return result
    from .palette import nearest
    palette_rgb=np.asarray(palette,dtype=np.uint8).reshape(256,3)
    rgb=rgba[painted,:3]
    unique,inverse=np.unique(rgb,axis=0,return_inverse=True)
    out=[]
    for triplet in unique:
        if exact:
            matches=np.where(np.all(palette_rgb[1:]==triplet,axis=1))[0]
            if not matches.size:
                raise ValueError(f'Non-palette artist colour: {list(map(int,triplet))}')
            out.append(int(matches[0]+1))
        else:
            out.append(nearest(triplet,palette))
    result[painted]=np.asarray(out,dtype=np.uint8)[inverse]
    if not np.array_equal(result!=0,surfaces.silhouette):
        raise AssertionError('Artist overlay changed alpha coverage')
    return result
