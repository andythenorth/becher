"""Generic placement coverage for compact three-part arrangements."""

import pytest

from src.composition import (
    candidates, packed_scene, draft, load_part, occupied_boxes, volumes_overlap,
    vocabularies,
)
from src.mesh.compile import compile_scene


def is_horizontal_tank(name):
    return name.startswith('storage_tank_horizontal_')


@pytest.mark.parametrize('building_tag', ['Industrial buildings', 'Compact process buildings'])
@pytest.mark.parametrize('silhouette', ['low', 'high'])
def test_horizontal_tank_building_triples_are_available(building_tag, silhouette):
    buildings = {name for names in vocabularies()[building_tag].values() for name in names}
    pool = candidates(['Liquid storage', building_tag], silhouette)
    examples = [scene for scene in pool.values()
                if len(scene['catalogue']['components']) == 3
                and any(is_horizontal_tank(n) for n in scene['catalogue']['components'])
                and any(n in buildings for n in scene['catalogue']['components'])]
    assert examples, (building_tag, silhouette)
    for scene in examples[:2]:
        mesh = compile_scene(scene)
        assert (mesh.vertices[..., :2] >= -1e-8).all()
        assert (mesh.vertices[..., :2] <= 1 + 1e-8).all()
        assert (mesh.vertices[..., 2] >= -1e-8).all()


def test_corner_packing_obeys_volume_collision_and_bounds():
    names = ('storage_tank_horizontal_low_01', 'liquid_pipe_run_straight_01',
             'storage_tank_small_low_01')
    parts = {name: load_part(name) for name in names}
    for axis in (0, 1):
        scene = packed_scene(parts, names, (0, 0, 0), axis)
        if scene is None:
            continue
        geometry = [s for s in scene['shapes'] if not s['id'] == 'slab']
        for shape in geometry:
            for volume in occupied_boxes(shape):
                assert min(volume[:2]) >= -1e-8
                assert max(volume[3:5]) <= 1 + 1e-8
        for a in geometry:
            for b in geometry:
                if a['id'].split('_')[1] == b['id'].split('_')[1]:
                    continue
                assert not any(volumes_overlap(u, v)
                               for u in occupied_boxes(a) for v in occupied_boxes(b))


def test_seeded_mixed_vocabulary_batches_are_reproducible():
    for tag in ('Industrial buildings', 'Compact process buildings'):
        for silhouette in ('low', 'high'):
            tags = ['Liquid storage', tag]
            assert draft(tags, 12345, silhouette) == draft(list(reversed(tags)), 12345, silhouette)
