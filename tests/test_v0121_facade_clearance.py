"""Native 1x doors/windows remain separate, flush and stable across rotations."""
from pathlib import Path
from dataclasses import replace
import numpy as np
from src.architectures import generate, library
from src.feature_passes import build_features, is_feature
from src.facade_profiles import panels, door_reservations, _wall_rect, _overlaps
from src.architectural_renderer import cast
from src.geometry import SURFACE_ROLES, MATERIAL_IDS

FAMILIES = Path(__file__).resolve().parents[1]/'examples'/'bof_industrial_facades.json'


def test_door_clearance_across_profiles_and_all_bof_fabric():
    for i in range(3):
        model=generate(1267,i,families=library(FAMILIES))
        for host in (c for c in model.components if c.role=='fabric'):
            spec=model.parameters['facade_profiles'][host.id]
            reserved=door_reservations(host,spec['doors'])
            windows=panels(host,'windows',spec['windows'],reserved=reserved)
            if spec['windows']!='blank':
                assert len(windows)>0, f'{host.id}: configured windows disappeared'
            for side,_,box,_ in windows:
                rect=_wall_rect(host,side,box)
                assert not any(side==dside and _overlaps(rect,drect,max(.018,(host.bounds[5]-host.bounds[2])*.035))
                               for dside,drect in reserved)


def test_decal_does_not_modify_depth_normals_or_scene_silhouette():
    model=generate(1267,0,families=library(FAMILIES))
    full=build_features(model)
    no_facades=replace(full,components=tuple(c for c in full.components
                    if not (is_feature(c,'windows') or is_feature(c,'doors'))))
    for angle in (0,90,180,270):
        baseline,_=cast(no_facades,angle,facade_mode='decals')
        decal,metrics=cast(full,angle,facade_mode='decals')
        np.testing.assert_array_equal(decal.depth,baseline.depth)
        np.testing.assert_array_equal(decal.normal,baseline.normal)
        np.testing.assert_array_equal(decal.silhouette,baseline.silhouette)
        assert metrics['facade_decal_pixels']>0
        # Frames must be visible in at least one view; this test separately
        # checks their material classification without requiring all doors
        # to be visible behind overlapping architectural masses.
        frame_ids=[int(pid) for pid,cid in metrics['primitive_components'].items()
                   if '/doors/' in cid and cid.endswith(':frame')]
        if angle in (90,180):
            assert np.count_nonzero(np.isin(decal.primitive,frame_ids)) > 0
        assert decal.validate()
