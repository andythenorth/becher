"""Exact TTD DOS indexed-palette utilities; no RGB export in sprite outputs."""
from pathlib import Path
import numpy as np
from PIL import Image


def load_palette(path=None):
    raw = (Path(path).read_bytes() if path else (Path(__file__).resolve().parents[1]/'data'/'ttd-dos.act').read_bytes())
    if len(raw) != 768:
        raise ValueError(f'ACT palette must contain exactly 768 bytes; got {len(raw)}')
    return list(raw)


def nearest(target, palette):
    rgb = np.asarray(palette, dtype=np.int32).reshape(256,3)
    t = np.asarray(target,dtype=np.int32)
    sq = np.sum((rgb-t)**2, axis=1)
    sq[0] = np.iinfo(np.int32).max
    return int(np.argmin(sq))


def ramp(values, palette):
    return np.array([nearest(rgb,palette) for rgb in values],dtype=np.uint8)


def indexed_image(pixels, palette):
    array=np.asarray(pixels)
    if array.shape!=(128,64) or array.dtype!=np.uint8:
        raise ValueError('Native 1x PNG requires uint8 pixels of shape (128,64)')
    image=Image.fromarray(array.copy(),mode='P')
    image.putpalette(palette)
    image.info['transparency']=0
    return image


def save_indexed(path,pixels,palette):
    dest=Path(path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    indexed_image(pixels,palette).save(dest,transparency=0)
    return dest


def open_indexed(path,palette):
    with Image.open(path) as image:
        if image.mode!='P' or image.size!=(64,128):
            raise ValueError(f'{path}: not 64x128 indexed PNG')
        if list(image.getpalette()[:768])!=list(palette):
            raise ValueError(f'{path}: different indexed palette')
        if image.info.get('transparency',0) not in (0,None):
            raise ValueError(f'{path}: transparency index must be 0')
        return np.asarray(image).copy()
