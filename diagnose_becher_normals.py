"""Run from the Becher repository root: python diagnose_becher_normals.py
Creates becher_normals_diagnostic.zip for inspection, without changing the repository.
"""
import hashlib
import io
import json
import os
import platform
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from src import pipeline
from src.mesh.compile import load_mesh


def sha(data):
    return hashlib.sha256(data).hexdigest()


def describe(values):
    a = np.asarray(values)
    result = {
        'shape': list(a.shape), 'dtype': str(a.dtype), 'sha256_raw': sha(np.ascontiguousarray(a).tobytes()),
    }
    if a.dtype.kind == 'f':
        result.update({
            'nan_count': int(np.isnan(a).sum()),
            'inf_count': int(np.isinf(a).sum()),
            'negative_zero_count': int((np.signbit(a) & (a == 0)).sum()),
            'minimum': float(np.min(a)), 'maximum': float(np.max(a)),
            'rounded_hashes': {str(n): sha(np.ascontiguousarray(np.round(a.astype(np.float64), n)).tobytes()) for n in (4, 6, 8, 10, 12)},
        })
        if a.ndim == 2 and a.shape[1] == 3:
            lengths = np.linalg.norm(a.astype(np.float64), axis=1)
            result['norm_length_min_max'] = [float(lengths.min()), float(lengths.max())]
            result['first_12_rows'] = a[:12].astype(float).tolist()
    return result


def main():
    root = Path.cwd()
    reference = json.loads((root / 'tests/golden/manifest.json').read_text())
    case = reference['cases']['diverse']
    report = {
        'python': sys.version, 'platform': platform.platform(),
        'numpy': np.__version__, 'working_directory': str(root),
        'build_options': case['build_options'], 'cases': {},
    }
    outzip = root / 'becher_normals_diagnostic.zip'
    with tempfile.TemporaryDirectory(prefix='becher-normals-') as temp, zipfile.ZipFile(outzip, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        path = Path(temp)
        pipeline.build(path, workers=1, buffers=True, **case['build_options'])
        manifest = pipeline._load_manifest(path)
        for key in sorted(manifest['candidates']):
            node = manifest['nodes'][manifest['candidates'][key]['current']]
            mesh = load_mesh(path / node['mesh'])
            expected = case['meshes'][key]
            entry = {}
            for name in ('vertices', 'normals', 'materials', 'component_ids'):
                array = np.ascontiguousarray(getattr(mesh, name))
                summary = describe(array)
                summary['baseline_sha256'] = expected[name]
                summary['matches_baseline'] = summary['sha256_raw'] == expected[name]
                entry[name] = summary
                buffer = io.BytesIO()
                np.save(buffer, array, allow_pickle=False)
                archive.writestr(f'diverse_{key}_{name}.npy', buffer.getvalue())
            report['cases'][key] = entry
        archive.writestr('report.json', json.dumps(report, indent=2, sort_keys=True))
    print('Diagnostic report:', outzip)
    for key, entry in report['cases'].items():
        print(f'Candidate {key}:')
        for name, value in entry.items():
            print(f'  {name}: {"MATCH" if value["matches_baseline"] else "DIFFERENT"} '
                  f'(shape={value["shape"]}, dtype={value["dtype"]})')
        print('  normals first rows:', entry['normals']['first_12_rows'])
    print('Please upload becher_normals_diagnostic.zip (the console log is optional).')


if __name__ == '__main__':
    main()
