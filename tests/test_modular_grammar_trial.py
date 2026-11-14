"""Experimental edge-spanning grammar acceptance, no renderer modifications."""
from pathlib import Path
from src.architectures import generate, library
from src.architectural_validation import validate
from src.feature_passes import build_features

GRAMMAR = Path(__file__).resolve().parents[1] / 'tests/fixtures/firs_grammar_candidates_v2.json'


def test_stable_exact_edge_span_and_valid_features():
    families = library(GRAMMAR)
    for i in range(32):
        building = generate(1267, i, families=families)
        main = next(c for c in building.components if c.id == 'main')
        axis = families[i % len(families)]['edge_span_axis']
        if axis == 'x':
            assert main.bounds[0] == 0.0 and main.bounds[3] == 1.0
        else:
            assert main.bounds[1] == 0.0 and main.bounds[4] == 1.0
        assert validate(building)['passes']
        assert validate(build_features(building))['passes']


def test_broad_lower_masses_and_roof_variety():
    families = library(GRAMMAR)
    kinds = set()
    for i in range(64):
        building = generate(1267, i, families=families)
        main = next(c for c in building.components if c.id == 'main')
        x0,y0,z0,x1,y1,z1 = main.bounds
        assert z1-z0 < max(x1-x0, y1-y0)
        kinds.update(c.roof for c in building.components if c.role == 'roof')
    assert {'flat', 'shed', 'gable_x', 'gable_y', 'monitor', 'sawtooth'} <= kinds
