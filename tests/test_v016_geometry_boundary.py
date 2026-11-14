"""0.16 contracts: one compiler, general frozen meshes, geometry-independent renderer."""
from pathlib import Path
import ast
import json
import subprocess
import sys
import numpy as np
import pytest
from PIL import Image
from src.mesh.author import revolution
from src.mesh.compile import compile_scene, save_mesh, load_mesh
from src.mesh.intersect import trace
from src.mesh.render import cast_mesh
from src.mesh.camera import rays


def test_revolution_normals_radial_and_caps():
    faces=revolution([(0,.2),(.5,.2),(1,.2)],segments=16)
    sides=[f for f in faces if np.ptp(f.xyz[:,2])>.1]
    assert sides
    assert all(np.abs(f.normals[:,2]).max()<1e-8 for f in sides)
    assert any((f.normals[0]==[0,0,-1]).all() for f in faces)
    assert any((f.normals[0]==[0,0,1]).all() for f in faces)


def test_sphere_is_surface_not_tubular_hoops():
    profile=[(.1,0),(.2,.2),(.4,.3),(.6,.2),(.7,0)]
    mesh=compile_scene({'shapes':[{'id':'sphere','type':'revolution','profile':profile}]})
    assert len(mesh.vertices)>100
    assert np.count_nonzero(np.abs(mesh.normals[:,:,2])>.1)>0
    assert np.allclose(np.linalg.norm(mesh.normals,axis=2),1)


@pytest.mark.parametrize('kind,shape',[
 ('box',{'type':'box','bounds':[.2,.2,.1,.8,.8,.9]}),
 ('cylinder',{'type':'cylinder','bounds':[.2,.2,.1,.8,.8,.9]}),
 ('beam',{'type':'beam','start':[.2,.2,.1],'end':[.8,.8,1.0],'thickness':.04}),
 ('revolution',{'type':'revolution','profile':[[.1,0],[.3,.2],[.5,.3],[.7,.2],[.9,0]]}),
 ('rings',{'type':'rings','rings':[[[.2,.2,.1],[.4,.2,.1],[.4,.4,.1],[.2,.4,.1]],[[.25,.25,.9],[.35,.25,.9],[.35,.35,.9],[.25,.35,.9]]]}),
 ('triangles',{'type':'triangles','vertices':[[[.2,.2,.1],[.7,.2,.1],[.3,.7,.7]]]}),
])
def test_frozen_scene_renders_all_four(kind,shape,tmp_path):
    mesh=compile_scene({'shapes':[shape]})
    f=tmp_path/'scene.npz';save_mesh(mesh,f)
    mesh=load_mesh(f)
    assert not mesh.vertices.flags.writeable
    for angle in (0,90,180,270):
        surface,_=cast_mesh(mesh,angle)
        surface.validate()
        assert np.count_nonzero(surface.material)>0,kind


def test_nearest_hit_independent_of_triangle_order():
    s={'shapes':[{'type':'box','id':'far','bounds':[.3,.3,.0,.7,.7,.2]},
                 {'type':'box','id':'near','bounds':[.3,.3,.3,.7,.7,.6]}]}
    mesh=compile_scene(s)
    o=np.array([[[.5,.5,2.]]]);direction=np.array([0,0,-1.])
    depth,*_=trace(mesh,o,direction)
    assert depth[0,0]==pytest.approx(1.4)


def test_mesh_scene_cli_roundtrip(tmp_path):
    scene=tmp_path/'scene.json'
    scene.write_text(json.dumps({'shapes':[{'type':'box','bounds':[.2,.2,.1,.7,.7,.8]}]}))
    project=Path(__file__).resolve().parents[1]
    import os
    env={**os.environ,'PYTHONPATH':str(project/'src')}
    frozen=tmp_path/'frozen.npz'
    subprocess.run([sys.executable,'-m','src','bake-scene','--input',str(scene),'--out',str(frozen)],env=env,check=True,capture_output=True)
    assert frozen.exists()
    out=tmp_path/'fourviews'
    subprocess.run([sys.executable,'-m','src','render-mesh','--mesh',str(frozen),'--out',str(out)],env=env,check=True,capture_output=True)
    for angle in (0,90,180,270):
        with Image.open(out/f'r{angle:03d}.png') as im:
            assert im.mode=='P' and im.size==(64,128)

# 0.16.1: Concave end caps must not cover the space outside the contour.
# The eight-vertex U is a single simply connected polygon (not a hole).
def _u_sweep_rings():
    contour=[(.2,.2),(.8,.2),(.8,.8),(.65,.8),
             (.65,.4),(.35,.4),(.35,.8),(.2,.8)]
    return [[[x,y,z] for x,y in contour] for z in (.2,.8)]


def test_concave_sweep_recess_is_empty_and_body_occludes():
    mesh=compile_scene({'shapes':[{'type':'rings','rings':_u_sweep_rings()}]})
    samples=[(.5,.65),(.5,.3),(.25,.65),(.75,.65),(.1,.1)]
    origins=np.array([[[x,y,2.] for x,y in samples]])
    depth,normal,material,part=trace(mesh,origins,np.array([0.,0.,-1.]))
    assert np.isinf(depth[0,[0,4]]).all()  # empty recess and outside
    assert np.allclose(depth[0,[1,2,3]],1.2)  # filled base and arms
    assert np.all(normal[0,[1,2,3],2]>.99)  # properly oriented top cap


def test_concave_sweep_side_normal_faces_into_recess():
    mesh=compile_scene({'shapes':[{'type':'rings','rings':_u_sweep_rings()}]})
    # Wall on right side of inner recess must face left, toward the void.
    origins=np.array([[[.5,.6,.5]]])
    depth,normal,*_=trace(mesh,origins,np.array([1.,0.,0.]))
    assert depth[0,0]==pytest.approx(.15)
    assert normal[0,0,0]<-.99


def test_concave_sweep_rotated_caps_are_equivalent():
    rings=np.asarray(_u_sweep_rings(),float)
    # Shift the end caps into a vertical YZ plane; their triangulation must
    # not depend on the preferred world axis.
    vertical=rings[:,:,[2,0,1]]
    mesh=compile_scene({'shapes':[{'type':'rings','rings':vertical.tolist()}]})
    origin=np.array([[[2.,.5,.65],[2.,.5,.3]]])
    depth,*_=trace(mesh,origin,np.array([-1.,0.,0.]))
    assert np.isinf(depth[0,0]);assert depth[0,1]==pytest.approx(1.2)


def test_concave_sweep_rejects_nonplanar_and_crossed_caps():
    from src.mesh.author import sweep_rings
    rings=_u_sweep_rings()
    warped=[[list(p) for p in ring] for ring in rings]
    warped[0][3][2]+=.02
    with pytest.raises(ValueError,match='planar'):
        sweep_rings(warped)
    bowtie=[(.2,.2),(.8,.8),(.2,.8),(.8,.2)]
    with pytest.raises(ValueError):
        sweep_rings([[[x,y,z] for x,y in bowtie] for z in (.2,.8)])
