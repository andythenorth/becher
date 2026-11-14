from collections import Counter
from http.server import ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import random
from threading import Thread
from urllib.request import Request, build_opener, ProxyHandler
from zipfile import ZipFile

from PIL import Image
import pytest

from src.composition import candidates, compose, draft, draw
from src.mesh.compile import compile_scene
from ui.__main__ import Handler, Review


GRAIN = ['Grain handling']
LIQUID = ['Liquid storage']
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('tags', [GRAIN, LIQUID, GRAIN + LIQUID])
@pytest.mark.parametrize('silhouette', ['low', 'high'])
def test_seeded_batches(tags, silhouette):
    first = draft(tags, 1267, silhouette)
    assert list(first) == [f'{row:02d}' for row in range(1, 17)]
    assert first == draft(list(reversed(tags)), 1267, silhouette)
    ids = lambda batch: {scene['catalogue']['composition'] for scene in batch.values()}
    assert ids(first) != ids(draft(tags, 4421, silhouette))
    for seed in range(30):
        metadata = [scene['catalogue'] for scene in draft(tags, seed, silhouette).values()]
        assert {entry['silhouette'] for entry in metadata} == {silhouette}
        assert max(Counter(entry['type'] for entry in metadata).values()) <= 12


def test_all_installed_compositions_compile_inside_tile():
    for silhouette in ('low', 'high'):
        for scene in candidates(GRAIN + LIQUID, silhouette).values():
            vertices = compile_scene(scene).vertices
            assert (vertices >= -1e-9).all()
            assert (vertices[..., :2] <= 1 + 1e-9).all()


def test_incompatible_storage_placement_is_rejected(monkeypatch):
    from src import composition
    parts = {name: composition.load_part(name) for name in ('gable_shed', 'tank')}
    monkeypatch.setitem(composition.PLANS, 'wall_pair', ((.5, .28, .81), (.37, .55), (.78,)))
    with pytest.raises(ValueError, match='incompatible footprints'):
        compose('gable_shed', 'wall_pair', 'tank', parts)


def test_cap_allows_skew_and_one_type_fallback():
    rng = random.Random(1)
    pool = {'a': {'catalogue': {'type': 'A'}}, 'b': {'catalogue': {'type': 'B'}}}
    assert draw(pool, ['a'] * 11, rng) == 'a'
    assert draw(pool, ['a'] * 12, rng) == 'b'
    assert draw({'a': pool['a']}, ['a'] * 15, rng) == 'a'


@pytest.fixture
def review_server(tmp_path):
    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        server.review = Review(tmp_path, ROOT)
        thread = Thread(target=server.serve_forever)
        thread.start()
        opener = build_opener(ProxyHandler({}))
        try:
            def request(path, data=None):
                url = f'http://127.0.0.1:{server.server_port}{path}'
                body = json.dumps(data).encode() if data is not None else None
                headers = {'Content-Type': 'application/json'} if body else {}
                with opener.open(Request(url, body, headers), timeout=90) as response:
                    return response.read()

            yield request
        finally:
            server.shutdown()
            thread.join()


def test_review_rerolls_only_one_row_and_exports_reproducible_batch(review_server, tmp_path):
    from src.authored_scenes import render_scene_files

    request = review_server
    brief = {'vocabularies': GRAIN, 'seed': 1267, 'silhouette': 'low'}
    first = json.loads(request('/compose', brief))
    assert first['can_reroll']
    reroll = {'batch': first['id'], 'candidate': '03'}
    updated = json.loads(request('/reroll', reroll))
    repeated = json.loads(request('/reroll', reroll))
    assert len(updated['candidates']) == 16
    assert updated['generated'] == repeated['generated']
    assert [entry['id'] for entry in updated['generated']] == [entry['id'] for entry in first['generated']]
    assert updated['generated'][2] != first['generated'][2]
    for index, row in enumerate(updated['candidates']):
        before = first['candidates'][index]
        assert [sprite['angle'] for sprite in row['sprites']] == [0, 90, 180, 270]
        if index != 2:
            assert row == before
        else:
            assert any(request(a['url']) != request(b['url'])
                       for a, b in zip(row['sprites'], before['sprites']))

    with ZipFile(BytesIO(request(f'/batch/{updated["id"]}.zip'))) as archive:
        assert len(archive.namelist()) == 80
        for row in updated['candidates']:
            key = row['key']
            geometry = archive.read(f'{key}_scene.json')
            assert request(f'/geometry/{updated["id"]}/{key}') == geometry
            for sprite in row['sprites']:
                filename = f'{key}_r{sprite["angle"]:03d}.png'
                assert archive.read(filename) == request(sprite['url'])
                with Image.open(BytesIO(archive.read(filename))) as image:
                    assert image.mode == 'P' and image.size == (64, 128)
        scene = tmp_path / 'export.json'
        scene.write_bytes(archive.read('03_scene.json'))
        render_scene_files({'03': scene}, tmp_path / 'reproduced')
        for angle in (0, 90, 180, 270):
            filename = f'r{angle:03d}.png'
            assert (tmp_path / 'reproduced' / '03' / filename).read_bytes() == archive.read(f'03_{filename}')
