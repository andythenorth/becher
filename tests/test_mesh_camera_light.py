"""Independent camera/light coordinate tests for mesh renderer."""
import numpy as np
import pytest
from src.mesh.camera import rotate_xy, rays
from src.lighting import SUN_FIVE

@pytest.mark.parametrize('turn,expected',[
    (0,(1.,2.,3.)),
    (90,(2.,-1.,3.)),
    (180,(-1.,-2.,3.)),
    (270,(-2.,1.,3.)),
])
def test_light_rotation_known_quarter_turns(turn,expected):
    assert np.allclose(rotate_xy((1.,2.,3.),turn),expected,atol=1e-14)

@pytest.mark.parametrize('turn',(0,90,180,270))
def test_light_dot_product_coordinate_equivalence(turn):
    # R(+angle) n dot L == n dot R(-angle) L.
    # This is a mathematical identity independent of the production renderer.
    n=np.array((.7,-.2,.4)); n/=np.linalg.norm(n)
    light=np.asarray(SUN_FIVE);light/=np.linalg.norm(light)
    inverse_light=rotate_xy(light,turn)
    rotated_normal=rotate_xy(n,(-turn)%360)
    assert np.dot(n,inverse_light)==pytest.approx(np.dot(rotated_normal,light),abs=1e-14)

@pytest.mark.parametrize('turn',(0,90,180,270))
def test_camera_and_light_use_same_coordinate_convention(turn):
    _,direction=rays(turn)
    _,reference=rays(0)
    assert np.allclose(direction,rotate_xy(reference,turn),atol=1e-14)

@pytest.mark.parametrize('turn',(0,90,180,270))
def test_world_geometry_unchanged_by_light_turn(turn):
    vec=np.asarray(SUN_FIVE,dtype=float)
    original=vec.copy()
    out=rotate_xy(vec,turn)
    assert np.array_equal(vec,original)
    assert np.isclose(np.linalg.norm(out),np.linalg.norm(vec))
