"""Deterministic family selection and same-family refill."""
import json

import pytest

from src.architectures import library
from src.architectural_validation import validate
from src.pipeline import build
from src.sampling import catalogue, create, candidates, select_families
from src.selection import vote, refill


def test_current_catalogues_and_defaults():
    primary, ancillary = catalogue()
    assert len(primary) == 6 and len(ancillary) == 5
    assert {family['category'] for family in ancillary} == {'ancillary'}
    assert select_families(primary, ancillary, None) == library()
    for family in primary + ancillary:
        for index in (0, 12, 41):
            assert validate(create(1267, index, [family]))['passes']


def test_selected_families_cycle_in_catalogue_order():
    primary, ancillary = catalogue()
    selected = select_families(primary, ancillary, ['tank_yard', 'broad_high_roof_hall'])
    models, _, _ = candidates(1267, 8, 0, selected, 96)
    replay, _, _ = candidates(1267, 8, 0, selected, 96)
    assert [model.family for model in models] == ['broad_high_roof_hall', 'tank_yard'] * 4
    assert [model.id for model in models] == [model.id for model in replay]
    assert len({model.parameters['variation']['aspect'] for model in models}) >= 2


def test_empty_and_unknown_selections_are_rejected():
    primary, ancillary = catalogue()
    with pytest.raises(ValueError, match='Select at least one family'):
        select_families(primary, ancillary, [])
    with pytest.raises(ValueError, match='Unknown family IDs: unknown'):
        select_families(primary, ancillary, ['tank_yard', 'unknown'])


def test_primary_edge_span_and_ancillary_are_contained():
    primary, ancillary = catalogue()
    families = primary + ancillary
    for index in range(44):
        model = create(1267, index, families)
        assert validate(model)['passes']
        family = families[index % len(families)]
        assert model.family == family['id']
        main = next(component for component in model.components if component.id == 'main')
        if family.get('edge_span_axis') == 'x':
            assert (main.bounds[0], main.bounds[3]) == (0.0, 1.0)
        if family.get('edge_span_axis') == 'y':
            assert (main.bounds[1], main.bounds[4]) == (0.0, 1.0)


def test_pipeline_refill_retains_selected_families(tmp_path):
    selected = ['broad_high_roof_hall', 'tank_yard']
    out = tmp_path / 'run'
    build(out, seed=1267, designs=4, workers=1, family_ids=selected,
          roof_colours='on', facade_mode='decals')
    original = json.loads((out / 'manifest.json').read_text())
    old = next(key for key, item in original['candidates'].items() if item['family'] == 'tank_yard')
    vote(out, reject=[old])
    new = refill(out, workers=1)['replaced'][old]
    updated = json.loads((out / 'manifest.json').read_text())
    candidate = updated['candidates'][new]
    assert candidate['family'] == 'tank_yard'
    assert updated['grammar_families'] == selected
    assert updated['roof_colours'] == 'on'
    assert len(updated['nodes'][candidate['current']]['sprites']) == 4
