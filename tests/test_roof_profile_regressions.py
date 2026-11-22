"""Source-level roof geometry regression checks; no runtime rendering hooks."""
from pathlib import Path
import json
import math

from src.composition import component_catalogue, load_part
from .roof_geometry_audit import analyse_component

# These faces are deliberate one-pixel northlight/sawtooth facets or a tiny
# clerestory cap that falls below the audit's useful native-pixel span.
KNOWN_UNOBSERVABLE = {
    ('foundry_monitor_broad', 'clerestory_cap'),
    ('mill_sawtooth_clad', 'sawtooth_0'),
    ('mill_sawtooth_clad', 'sawtooth_1'),
    ('sawtooth_hall', 'bay_0'),
    ('sawtooth_hall', 'bay_1'),
}
FRONT_TARGET = 1.0
FRONT_TOLERANCE = 0.075
REAR_TOLERANCE = 0.075
MAX_AUTHORED_Z = 1.2


def roof_slope_conforms(role, slope):
    if slope is None:
        return True
    if role == 'front':
        return abs(slope - FRONT_TARGET) <= FRONT_TOLERANCE
    if role == 'rear':
        return slope <= REAR_TOLERANCE
    return True


def test_all_authored_pitched_roofs_conform_or_are_explicitly_unobservable():
    failures = []
    for name in component_catalogue():
        records, _, _ = analyse_component(name, load_part(name), render_rasters=False)
        for record in records:
            if record['source_shape_type'] != 'rings':
                continue
            if (name, record['part']) in KNOWN_UNOBSERVABLE:
                continue
            for view in record['rotations']:
                if not roof_slope_conforms(view['role'], view['slope']):
                    failures.append((name, record['part'], view['rotation'],
                                     view['role'], view['slope']))
    assert not failures, failures


def test_authored_ring_geometry_has_finite_bounded_heights_and_matched_sections():
    failures = []
    for name in component_catalogue():
        part = load_part(name)
        for shape in part.get('shapes', []):
            if shape.get('type') != 'rings':
                continue
            rings = shape.get('rings', [])
            if len({len(ring) for ring in rings}) > 1:
                failures.append((name, shape['id'], 'section vertex counts differ'))
            for ring in rings:
                for vertex in ring:
                    if not all(math.isfinite(value) for value in vertex):
                        failures.append((name, shape['id'], 'non-finite vertex'))
                    if vertex[2] < 0 or vertex[2] > MAX_AUTHORED_Z:
                        failures.append((name, shape['id'], 'pathological height', vertex[2]))
    assert not failures, failures


def test_slope_gate_rejects_pathological_control_values():
    assert roof_slope_conforms('front', 1.0)
    assert not roof_slope_conforms('front', 1.35)
    assert not roof_slope_conforms('rear', 0.25)
