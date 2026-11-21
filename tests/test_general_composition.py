"""Role-independent fixed-geometry composition regression tests."""
import pytest

from src.composition import (arbitrary_scene, candidates, load_part,
                             rigid_place, occupied_boxes, volumes_overlap,
                             vocabularies)
from src.mesh.compile import compile_scene


def test_reviewed_headframe_can_combine_with_chimney_from_another_vocabulary():
    pool = candidates(['Mining and aggregates','Chimneys'],'high')
    mining_annexes = vocabularies()['Mining and aggregates']['annexes']
    headframes = {name for name in mining_annexes
                  if name == 'quarry_final_balanced_headframe'
                  or name.startswith('quarry_headframe_')}
    assert 'quarry_final_balanced_headframe' in headframes
    assert 'mine_headframe' not in mining_annexes
    examples = [scene for scene in pool.values()
                if 'chimney_low_tapered' in scene['catalogue']['components']
                and headframes.intersection(scene['catalogue']['components'])]
    assert examples, 'A current headframe and chimney must be able to share a tile'
    mesh = compile_scene(examples[0])
    assert (mesh.vertices[..., :2] >= -1e-8).all()
    assert (mesh.vertices[..., :2] <= 1+1e-8).all()


def test_arbitrary_roles_and_repeats():
    parts = {name:load_part(name) for name in ('tank','chimney_low_tapered')}
    scene = arbitrary_scene((('tank',.25,.25,0),('tank',.75,.75,0),
                             ('chimney_low_tapered',.75,.25,0)),parts)
    assert len(scene['catalogue']['components']) == 3
    assert scene['catalogue']['components'].count('tank') == 2


def test_3d_collision_ignores_separated_heights_and_rejects_intersections():
    solid = {'type':'box','bounds':[.2,.2,.1,.4,.4,.3]}
    elevated = {'type':'box','bounds':[.2,.2,.4,.4,.4,.5]}
    intersect = {'type':'box','bounds':[.3,.3,.2,.5,.5,.4]}
    a = occupied_boxes(solid)[0]
    assert not volumes_overlap(a,occupied_boxes(elevated)[0])
    assert volumes_overlap(a,occupied_boxes(intersect)[0])


def test_rigid_rotation_preserves_dimensions():
    part = load_part('short_inclined_conveyor')
    original = rigid_place(part,'a_',(.5,.5),0)
    turned = rigid_place(part,'b_',(.5,.5),1)
    assert len(original) == len(turned)
    assert {s['type'] for s in original} == {s['type'] for s in turned}
    compile_scene({'shapes':turned})


def test_same_site_collision_rejected():
    parts={'tank':load_part('tank')}
    with pytest.raises(ValueError,match='Incompatible geometry'):
        arbitrary_scene((('tank',.5,.5,0),('tank',.5,.5,0)),parts)


def test_packing_uses_actual_footprints_not_original_centres():
    from src.composition import packed_sites, packed_scene
    parts = {n: load_part(n) for n in ('tank','chimney_low_tapered')}
    sites = packed_sites(parts, ('tank','chimney_low_tapered'), (0,0), 0)
    assert sites is not None and sites[0] != sites[1]
    scene = packed_scene(parts, ('tank','chimney_low_tapered'), (0,0), 0)
    assert scene is not None
    assert len(scene['catalogue']['components']) == 2


def test_slab_not_collision_checked_but_component_base_is():
    from src.composition import valid_addition
    # A local footing is an ordinary shape, so another solid intersecting it
    # is rejected; the shared tile slab is not supplied to occupied geometry.
    footing = {'id':'footing','type':'box','bounds':[.2,.2,.044,.4,.4,.09]}
    intruder = {'id':'intruder','type':'box','bounds':[.25,.25,.07,.35,.35,.12]}
    occupied = occupied_boxes(footing)
    assert not valid_addition([intruder],occupied,(.25,.25,.35,.35))
    assert valid_addition([intruder],[],(.25,.25,.35,.35))


def test_all_quarter_turns_are_available_for_packing():
    from src.composition import packed_scene
    parts = {n: load_part(n) for n in ('tank','chimney_low_tapered')}
    for turns in range(4):
        scene = packed_scene(parts,('tank','chimney_low_tapered'),(0,turns),0)
        assert scene is not None


def test_tile_designs_can_share_a_tile_when_their_footprints_fit(monkeypatch):
    from src import composition

    def part(name, width, placement=None):
        half = width / 2
        footprint = [-half, -half, half, half]
        return {
            'placement': placement,
            'footprint': footprint,
            'shapes': [{'id': name, 'type': 'box', 'material': 'metal',
                        'bounds': [-half, -half, 0, half, half, .2]}],
        }

    parts = {
        'compact_wrapped_block': part('compact', .60, 'tile'),
        'wide_wrapped_block': part('wide', .97, 'tile'),
        'small_chimney': part('chimney', .12),
    }
    monkeypatch.setattr(composition, 'load_part', parts.__getitem__)
    pool = composition._general_candidates(tuple(parts), 'low')
    teams = [scene['catalogue']['components'] for scene in pool.values()]
    assert ['compact_wrapped_block', 'small_chimney'] in teams
    assert [team for team in teams if 'wide_wrapped_block' in team] == [['wide_wrapped_block']]
