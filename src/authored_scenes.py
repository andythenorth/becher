"""Discover installed scene JSON and render it through the mesh compiler."""

from concurrent.futures import ProcessPoolExecutor
import json
import os
import shutil
from pathlib import Path
import re

from .mesh.compile import compile_scene
from .mesh.io import save
from .mesh.render import cast_mesh


SCENE_DIRECTORY = Path(__file__).resolve().parents[1] / 'data' / 'scenes'
SCENE_ID = re.compile(r'[a-z0-9][a-z0-9_]*')


def scene_catalogue():
    return {
        path.stem: path
        for path in sorted(SCENE_DIRECTORY.glob('*.json'))
        if SCENE_ID.fullmatch(path.stem) and path.is_file()
    }


CATALOGUE_FIELDS = ('label', 'layout', 'ancillary', 'hall_height', 'ancillary_height',
                    'composition', 'silhouette')


def list_scenes():
    entries = []
    for key, path in scene_catalogue().items():
        entry = {'id': key, 'label': key.replace('_', ' ')}
        try:
            scene = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            # Keep a broken file visible so rendering can report its exact error.
            entries.append(entry)
            continue
        metadata = scene.get('catalogue') if isinstance(scene, dict) else None
        if isinstance(metadata, dict):
            for field in CATALOGUE_FIELDS:
                value = metadata.get(field)
                if isinstance(value, str) and value.strip():
                    entry[field] = value.strip()
            vocabularies = metadata.get('vocabularies')
            if isinstance(vocabularies, list):
                entry['vocabularies'] = list(dict.fromkeys(
                    value.strip() for value in vocabularies
                    if isinstance(value, str) and value.strip()
                ))
        entries.append(entry)
    return entries


def render_scene(scene_id, output):
    path = scene_catalogue().get(scene_id)
    if path is None:
        raise ValueError(f'Unknown installed scene: {scene_id}')
    _render_scene_file(path, output)
    return {'id': scene_id, 'sprites': 4}


def _render_scene_file(path, output):
    render_geometry(json.loads(path.read_text(encoding='utf-8')), output)


def render_geometry(scene, output):
    mesh = compile_scene(scene)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for rotation in (0, 90, 180, 270):
        surface, _ = cast_mesh(mesh, rotation)
        save(surface, output / f'r{rotation:03d}.png', buffers=False)


def _render_scene_job(job):
    source, target = job
    try:
        _render_scene_file(source, target)
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise ValueError(f'{source.stem}: {error}') from error


def render_scenes(scene_ids, output, workers=None):
    catalogue = scene_catalogue()
    if not scene_ids or len(set(scene_ids)) != len(scene_ids):
        raise ValueError('Choose at least one scene, each only once')
    for scene in scene_ids:
        if scene not in catalogue:
            raise ValueError(f'Unknown installed scene: {scene}')
    return render_scene_files({scene: catalogue[scene] for scene in scene_ids}, output, workers)


def render_scene_files(sources, output, workers=None):
    scene_ids = list(sources)
    if workers is None:
        workers = min(4, os.cpu_count() or 1)
    if workers < 1:
        raise ValueError('Workers must be positive')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    try:
        jobs = [(source, output / scene) for scene, source in sources.items()]
        if workers == 1 or len(jobs) == 1:
            for job in jobs:
                _render_scene_job(job)
        else:
            with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
                list(pool.map(_render_scene_job, jobs))
    except BaseException:
        shutil.rmtree(output)
        raise
    return {'scenes': scene_ids, 'sprites': len(scene_ids) * 4}
