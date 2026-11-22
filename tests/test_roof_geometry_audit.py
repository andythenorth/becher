"""Offline roof conformance diagnostics; no changes to normal render paths."""
from copy import deepcopy
import math

import numpy as np

from .roof_geometry_audit import analyse_component, project_delta
from src.composition import load_part


def _slope(vec, rotation=0):
    dx, dy = project_delta(vec, rotation)
    return abs(dy/dx)


def test_canonical_dimetric_pitch_has_one_to_one_front_and_horizontal_back():
    assert math.isclose(_slope((0,1,-4/9)),1,abs_tol=1e-9)
    assert math.isclose(_slope((0,-1,-4/9)),0,abs_tol=1e-9)
    # Orthogonal roof axes obey the same requirement under camera rotation.
    assert math.isclose(_slope((1,0,-4/9), 90),1,abs_tol=1e-9)
    assert math.isclose(_slope((-1,0,-4/9), 90),0,abs_tol=1e-9)


def test_corrected_mill_gable_has_analytic_pitch_conformance():
    faces, _, status = analyse_component('mill_steel_gable_long',load_part('mill_steel_gable_long'),render_rasters=False)
    assert status == 'pitched'
    assert len(faces)==2
    assert all(face['verdict']=='ANALYTIC_OK' for face in faces)
    assert all(any(view['role']=='front' and abs(view['slope']-1.0)<=.075 for view in face['rotations']) for face in faces)


def test_existing_foundry_main_roof_is_analytic_reference():
    faces,_,_ = analyse_component('foundry_monitor_broad',load_part('foundry_monitor_broad'),render_rasters=False)
    main = [face for face in faces if face['part']=='main_gable']
    assert len(main)==2
    assert all(face['verdict']=='ANALYTIC_OK' for face in main)
    assert all(any(view['role']=='front' and abs(view['slope']-1)<.01 for view in face['rotations']) for face in main)


def test_offline_ridge_height_correction_changes_measured_geometry():
    part=deepcopy(load_part('mill_steel_gable_long'))
    roof=next(s for s in part['shapes'] if s['id']=='steel_gable')
    for ring in roof['rings']:
        ring[3][2]=.47+(2/9)*(.428)
    faces,_,_ = analyse_component('adjusted_mill',part,render_rasters=False)
    assert len(faces)==2
    assert all(face['verdict']=='ANALYTIC_OK' for face in faces)


def test_flat_roof_does_not_enter_pitched_roof_audit():
    faces,_,status=analyse_component('dispatch_shed',load_part('dispatch_shed'),render_rasters=False)
    assert status == 'no_pitched'
    assert faces == []
