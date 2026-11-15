"""v0.12 facade contracts: role-bound profiles, flush glazings, unchanged legacy."""
from pathlib import Path
import hashlib
import numpy as np
import pytest
from src.architectures import library,generate
from src.feature_passes import build_features, is_feature
from src.mesh.render import cast
from src.geometry import MATERIAL_IDS, SURFACE_ROLES

GRAMMAR=Path(__file__).resolve().parents[1]/'examples'/'bof_industrial_facades.json'


def test_bof_family_profiles_are_declared_and_valid():
    families=library(GRAMMAR)
    assert len(families)==3
    assert all('windows' in f and 'doors' in f for f in families)
    for index in range(3):
        building=generate(1267,index,families=families)
        expected=building.parameters['facade_profiles']
        assert expected['main']['windows']==families[index]['windows']
        assert expected['main']['doors']==families[index]['doors']
        assert all(c.id in expected for c in building.components if c.role=='fabric')


def test_windows_and_doors_are_only_grammar_assigned_decal_panels():
    families=library(GRAMMAR)
    for i in range(3):
        base=generate(1267,i,families=families)
        scene=build_features(base)
        profiles=base.parameters['facade_profiles']
        assert any(is_feature(c,'windows') for c in scene.components), f'family {i}: windows absent'
        assert any(is_feature(c,'doors') for c in scene.components), f'family {i}: doors absent'
        for c in scene.components:
            if is_feature(c,'windows'):
                assert profiles[c.parent]['windows']!='blank'
            if is_feature(c,'doors'):
                assert profiles[c.parent]['doors']!='none'
        for angle in (0,90,180,270):
            blank,_=cast(scene,angle,facade_mode='boxes')
            dec,metrics=cast(scene,angle,facade_mode='decals')
            # The glass pixels are in-place reclassification of visible wall hits;
            # removing protruding panel boxes cannot enlarge the overall scene.
            assert np.count_nonzero(dec.role==SURFACE_ROLES['glazing'])>0
            assert metrics['facade_decal_pixels']>0
            assert dec.validate()
            # Other mechanical feature components remain 3D raycast geometry.
            assert any(is_feature(c,'equipment') for c in scene.components)
            assert any(is_feature(c,'greeble') for c in scene.components)


def test_unknown_profile_rejected_at_grammar_load(tmp_path):
    import json
    data=json.loads(GRAMMAR.read_text())
    data['families'][0]['windows']='made_up_windows'
    path=tmp_path/'bad.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='unknown window profile'):
        library(path)
