"""Approved v0.16.4 output oracle. Never regenerate in an ordinary test run.

Frozen building scenes exercise mesh compilation and raster output.
Fixture hashes authenticate the inputs against the original baseline. A failed
pixel comparison emits a 4x nearest-neighbour diagnostic diff in tmp_path.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src import pipeline
from src.mesh.compile import load_mesh

ROOT=Path(__file__).parent/'golden'
REFERENCE=json.loads((ROOT/'manifest.json').read_text())

def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def assert_complete_sprite_coverage(manifest, case, mode):
    """Verify the expected key space before examining any sprite bytes."""
    rotations = {0, 90, 180, 270}
    expected_candidates = set(case['meshes'])
    assert set(manifest['candidates']) == expected_candidates, f'{mode}: candidate set differs'
    assert set(case['scenes']) == expected_candidates, f'{mode}: scene references incomplete'
    expected_names = {f'{key}_{angle:03d}' for key in expected_candidates for angle in rotations}
    assert set(case['images']) == expected_names, f'{mode}: golden references incomplete'
    actual_names = []
    for key in expected_candidates:
        node_id = manifest['candidates'][key]['current']
        records = manifest['nodes'][node_id]['sprites']
        actual_names.extend(f'{key}_{int(r["rotation"]):03d}' for r in records)
    assert len(actual_names) == len(expected_names), f'{mode}: missing/duplicate sprite records'
    assert set(actual_names) == expected_names, f'{mode}: incorrect candidate/rotation coverage'
    return expected_names

FLOAT_ATOL = 1e-12  # Cross-platform float64 rounding; rtol intentionally zero.


def assert_frozen_mesh_floats(mesh, mesh_record, mode, key):
    """Numerical mesh oracle against original, hash-authenticated float arrays.

    Do not recapture these fixtures from the code under test. The original
    reference hashes remain the authority for the stored baseline arrays.
    """
    fixture = ROOT / f'{mode}_{key}_geometry.npz'
    with np.load(fixture, allow_pickle=False) as frozen:
        assert set(frozen.files) == {'vertices', 'normals'}, f'{mode}/{key}: incomplete float fixture'
        for member in ('vertices', 'normals'):
            expected = frozen[member]
            actual = getattr(mesh, member)
            expected_hash = digest(np.ascontiguousarray(expected).tobytes())
            assert expected_hash == mesh_record[member], f'{mode}/{key}: frozen {member} fixture modified'
            assert actual.shape == expected.shape, f'{mode}/{key}: {member} shape differs'
            assert actual.dtype == expected.dtype, f'{mode}/{key}: {member} dtype differs'
            assert np.isfinite(actual).all(), f'{mode}/{key}: {member} contains nonfinite values'
            assert np.allclose(actual, expected, atol=FLOAT_ATOL, rtol=0), (
                f'{mode}/{key}: mesh {member} differs beyond {FLOAT_ATOL:g}; '
                f'max absolute error {np.max(np.abs(actual - expected)):.3g}'
            )


def test_frozen_float_oracle_rejects_geometry_mutation():
    """A meaningful change in a vertex or normal must fail the float oracle."""
    from types import SimpleNamespace
    case = REFERENCE['cases']['diverse']['meshes']['0000']
    with np.load(ROOT / 'diverse_0000_geometry.npz', allow_pickle=False) as frozen:
        original = SimpleNamespace(vertices=frozen['vertices'].copy(), normals=frozen['normals'].copy())
    assert_frozen_mesh_floats(original, case, 'diverse', '0000')
    for member in ('vertices', 'normals'):
        altered = SimpleNamespace(vertices=original.vertices.copy(), normals=original.normals.copy())
        getattr(altered, member)[0, 0, 0] += 2e-3
        with pytest.raises(AssertionError, match=f'mesh {member} differs'):
            assert_frozen_mesh_floats(altered, case, 'diverse', '0000')
    # Last-bit noise is tolerated without modifying the frozen fixture.
    rounded = SimpleNamespace(vertices=original.vertices.copy(), normals=original.normals.copy())
    rounded.normals[0, 0, 0] += 3e-16
    assert_frozen_mesh_floats(rounded, case, 'diverse', '0000')


@pytest.mark.golden
@pytest.mark.parametrize('mode',tuple(REFERENCE['cases']))
def test_approved_sprites_geometry_and_scene(mode,tmp_path):
    case=REFERENCE['cases'][mode]
    output=tmp_path/mode
    manifest = {'candidates': {}, 'nodes': {}}
    items = []
    for key, scene_hash in case['scenes'].items():
        scene = json.loads((ROOT / f'{mode}_{key}_scene.json').read_text())
        actual = digest(json.dumps(scene, sort_keys=True, separators=(',', ':')).encode())
        assert actual == scene_hash, f'{mode}/{key}: frozen scene modified'
        node = {'id': key}
        items.append((node, pipeline.scene_from_dict(scene)))
        manifest['candidates'][key] = {'current': key}
        manifest['nodes'][key] = node
    pipeline._render_nodes(items, output, workers=1, buffers=False, **case['render_options'])
    expected_names = assert_complete_sprite_coverage(manifest, case, mode)
    for key in sorted(manifest['candidates']):
        node=manifest['nodes'][manifest['candidates'][key]['current']]
        mesh=load_mesh(output/node['mesh'])
        mesh_record=case['meshes'][key]
        assert_frozen_mesh_floats(mesh, mesh_record, mode, key)
        for member in ('materials', 'component_ids'):
            actual=digest(np.ascontiguousarray(getattr(mesh,member)).tobytes())
            assert actual==mesh_record[member],f'{mode}/{key}: mesh {member} changed'
        assert len(mesh.vertices)==mesh_record['triangle_count']
        assert digest(json.dumps(mesh.component_names).encode())==mesh_record['component_names']
        for record in node['sprites']:
            angle=int(record['rotation'])
            name=f'{key}_{angle:03d}'
            assert name in expected_names
            expected=case['images'][name]
            with Image.open(ROOT/expected['file']) as reference:
                assert reference.mode=='P'
                reference_pixels=np.asarray(reference).copy()
                assert digest(reference_pixels.tobytes())==expected['pixels_sha256'],f'{name}: reference image modified'
                assert digest(bytes(reference.getpalette()))==expected['palette_sha256']
            with Image.open(output/record['file']) as produced:
                assert produced.mode=='P' and produced.size==(64,128)
                pixels=np.asarray(produced).copy()
                assert digest(bytes(produced.getpalette()))==expected['palette_sha256'],f'{mode}/{name}: palette differs'
            if not np.array_equal(pixels,reference_pixels):
                # Diagnostic is created only on a failed comparison; it does not
                # weaken the strict native indexed-pixel assertion.
                difference=(pixels!=reference_pixels).astype(np.uint8)*255
                Image.fromarray(difference).resize((256,512),Image.Resampling.NEAREST).save(tmp_path/f'{mode}_{name}_DIFF.png')
                count=int(np.count_nonzero(difference))
                pytest.fail(f'{mode}/{name}: {count} indexed pixels differ; diff: {tmp_path}/{mode}_{name}_DIFF.png')
            assert digest(pixels.tobytes())==expected['pixels_sha256']
