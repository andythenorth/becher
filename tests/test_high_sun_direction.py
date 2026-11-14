"""Regression for the high, screen-relative five-o'clock lighting requirement."""
import numpy as np
import pytest
from src.lighting import SUN_FIVE, quantize
from src.mesh.camera import rotate_xy
from src.geometry import VisibleSurfaces, MATERIAL_IDS

def band_for(normal, turn):
    n = np.asarray(normal, dtype=np.float32)
    n = np.broadcast_to(n,(1,1,3)).copy()
    material = np.full((1,1),MATERIAL_IDS['concrete'],dtype=np.uint8)
    depth = np.ones((1,1),dtype=np.float32)
    part = np.ones((1,1),dtype=np.int32)
    refs = np.ones((1,1),dtype=np.uint8)
    surface = VisibleSurfaces(material,n,depth,part,refs)
    return int(quantize(surface, light=rotate_xy(SUN_FIVE,turn))[0,0])

@pytest.mark.parametrize('turn',(0,90,180,270))
def test_high_sun_top_brighter_than_visible_walls(turn):
    # For each view, one of each XY wall orientation is exposed.
    top = band_for((0,0,1),turn)
    walls = [band_for(tuple(rotate_xy(v,turn)),turn) for v in ((1,0,0),(0,1,0))]
    assert top > max(walls), (top,walls)

@pytest.mark.parametrize('turn',(0,90,180,270))
def test_screen_relative_brightness_stable_across_rotations(turn):
    for normal in ((0,0,1),(1,0,0),(0,1,0)):
        assert band_for(tuple(rotate_xy(normal,turn)),turn)==band_for(normal,0)

def test_sun_is_significantly_elevated():
    light=np.asarray(SUN_FIVE,dtype=float)
    assert light[2] > np.hypot(light[0],light[1])
