"""Regression coverage for curated liquid tank catalogues and horizontal shapes."""
import pytest
from src.composition import candidates, draft, load_part, vocabularies
from src.mesh.compile import compile_scene

def tank(name): return load_part(name).get('role') == 'tank'

@pytest.mark.parametrize('tag', ['Liquid storage', 'Liquid processing'])
@pytest.mark.parametrize('silhouette', ['low', 'high'])
def test_tanks_exist_and_compile(tag,silhouette):
    pool=candidates([tag],silhouette)
    tank_scenes=[s for s in pool.values() if any(tank(n) for n in s['catalogue']['components'])]
    assert len(tank_scenes)>=20
    for scene in tank_scenes[:3]:
        mesh=compile_scene(scene)
        assert (mesh.vertices[..., :2]>=-1e-8).all()
        assert (mesh.vertices[..., :2]<=1+1e-8).all()

@pytest.mark.parametrize('silhouette',['low','high'])
def test_storage_tanks_combine_with_other_structures(silhouette):
    totals=[]
    for seed in range(20):
        result=draft(['Liquid storage'],seed,silhouette)
        mixed=sum(any(tank(n) for n in scene['catalogue']['components']) and
                  any(not tank(n) for n in scene['catalogue']['components'])
                  for scene in result.values())
        totals.append(mixed)
    assert sum(totals)/len(totals)>=6

@pytest.mark.parametrize('tag',['Liquid storage','Liquid processing'])
@pytest.mark.parametrize('silhouette',['low','high'])
def test_no_mixed_tank_design_compositions(tag,silhouette):
    pool=candidates([tag],silhouette)
    assert all(len({n for n in scene['catalogue']['components'] if tank(n)})<=1 for scene in pool.values())


def test_curated_tank_catalogue_and_profiles():
    groups=vocabularies()
    storage=groups['Liquid storage']['storage']
    assert 16<=len(storage)<=26
    assert any(n.startswith('storage_tank_horizontal_pair_low_') for n in storage)
    assert any(n.startswith('storage_tank_horizontal_pair_high_') for n in storage)
    assert any(n.startswith('storage_tank_horizontal_stack_high_') for n in storage)
    assert len(groups['Liquid processing']['storage'])<=16


def test_horizontal_tanks_are_unambiguous_cylindrical_bodies():
    groups=vocabularies()
    horizontal=[n for n in groups['Liquid storage']['storage'] if n.startswith('storage_tank_horizontal_')]
    assert len(horizontal)>=6
    for name in horizontal:
        part=load_part(name)
        sweeps=[s for s in part['shapes'] if s['type']=='rings' and s['id'].startswith('vessel_')]
        assert sweeps
        for body in sweeps:
            assert len(body['rings'])>=6
            # The two long stations have the full cylinder radius.
            assert len(body['rings'][2])>=16
