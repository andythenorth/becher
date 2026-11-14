"""New renderer tests: mathematical facts, not historical image-hash worship."""
from pathlib import Path
import ast
import numpy as np
import pytest
from src.mesh.solids import box, cylinder
from src.mesh.compile import Mesh, compile_building, save_mesh, load_mesh
from src.mesh.camera import rays
from src.mesh.intersect import trace
from src.mesh.render import cast
from src.architectures import generate
from src.feature_passes import build_features


def test_box_outward_normals():
    faces=box((0,0,0,1,1,1),'concrete','cube')
    assert len(faces)==12
    for f in faces:
        ctr=f.xyz.mean(axis=0)
        outward=ctr-np.array([.5,.5,.5])
        assert np.dot(f.normals[0],outward) > 0


def test_cylinder_side_normals_and_caps():
    faces=cylinder((-.5,-.5,0,.5,.5,1),'metal','vessel',segments=16)
    assert len(faces)==64
    for f in faces:
        if np.ptp(f.xyz[:,2])>.5:  # a curved side triangle
            assert np.max(np.abs(f.normals[:,2]))<1e-10
            assert np.allclose(np.linalg.norm(f.normals,axis=1),1)


def test_generic_occlusion_not_scene_order():
    close=box((-.5,-.5,1,.5,.5,2),'metal','near')
    far=box((-.5,-.5,-2,.5,.5,-1),'roof','far')
    def scene(parts):
        return Mesh(np.array([f.xyz for f in parts]),np.array([f.normals for f in parts]),
                    np.array([1 if f.part=='near' else 2 for f in parts],np.uint8),
                    np.array([1 if f.part=='near' else 2 for f in parts],np.uint16),('near','far'))
    origin=np.array([[[0,0,4]]],dtype=float)
    direction=np.array([0,0,-1],float)
    for members in (far+close,close+far):
        depth,normal,material,part=trace(scene(members),origin,direction)
        assert part[0,0]==1
        assert abs(depth[0,0]-2)<1e-9
        assert np.allclose(normal[0,0],[0,0,1])


def test_camera_rotation_does_not_modify_baked_world_normals():
    mesh=compile_building(generate(1267,0))
    before=mesh.normals.copy()
    for deg in (0,90,180,270):
        o,d=rays(deg)
        assert o.shape==(128,64,3)
        assert d.shape==(3,)
    assert np.array_equal(mesh.normals,before)
    assert not mesh.normals.flags.writeable


def test_mesh_bake_roundtrip(tmp_path):
    mesh=compile_building(generate(1267,0))
    path=tmp_path/'frozen.npz'
    save_mesh(mesh,path)
    restored=load_mesh(path)
    for name in ('vertices','normals','materials','component_ids'):
        assert np.array_equal(getattr(mesh,name),getattr(restored,name))
    assert mesh.component_names==restored.component_names


@pytest.mark.parametrize('index',range(6))
@pytest.mark.parametrize('rotation',(0,90,180,270))
def test_factory_render_contract(index,rotation):
    building=build_features(generate(1267,index))
    fresh,_=cast(building,rotation,facade_mode='decals')
    assert fresh.validate()
    assert fresh.material.shape==(128,64)
    assert np.count_nonzero(fresh.material)>100
    assert np.array_equal(fresh.material>0,fresh.reference_pixels>0)


def test_pipeline_freezes_once_and_prevents_backend_cache_collision(tmp_path):
    from src.pipeline import build
    out=tmp_path/'run'
    metrics=build(out,seed=1267,designs=1,workers=1,renderer='mesh',
                  semantic_colour='off',roof_colours='off',facade_mode='decals')
    assert metrics['sprites']==4
    frozen=list(out.glob('nodes/*/mesh.npz'))
    assert len(frozen)==1
    mesh=load_mesh(frozen[0])
    assert len(mesh.vertices)>0
    assert len(list(out.glob('nodes/*/r???.png')))==4
    with pytest.raises(ValueError,match='only renderer=mesh'):
        build(tmp_path/'another',seed=1267,designs=1,workers=1,renderer='analytic')


