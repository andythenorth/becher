"""Independent v0.15 oracles for new structural sampling and ancillary catalogue."""
import json
from pathlib import Path
import tempfile
from collections import Counter
import numpy as np
from PIL import Image
from src.architectures import library
from src.architectural_validation import validate
from src.sampling import catalogue, create, candidates, structural_distance
from src.pipeline import build
from src.selection import vote, refill


def test_current_catalogues_and_defaults():
    primary,ancillary=catalogue()
    assert len(primary)==6 and len(ancillary)==5
    assert {f['category'] for f in ancillary}=={'ancillary'}
    assert {f['id'] for f in primary}=={f['id'] for f in library()}
    for family in primary+ancillary:
        for i in (0,12,41):
            item=create(1267,i,primary=[family],ancillary=ancillary,
                        mode='diverse') if family in primary else create(1267,i,
                        primary=primary,ancillary=[family],mode='diverse')
            assert validate(item)['passes']


def test_related_50_50_and_variable_halls():
    p,a=catalogue()
    industry=p[3]['id']
    models,_,_=candidates(1267,12,0,p,a,'related',industry,144)
    assert len(models)==12
    assert sum(m.family==industry for m in models)==6
    assert sum(m.parameters.get('grammar_category')=='ancillary' for m in models)==6
    assert len({m.parameters['variation']['arrangement'] for m in models if m.family==industry})>=2
    for m in models: assert validate(m)['passes']


def test_diverse_is_reproducible_and_stronger_than_first_twelve():
    p,a=catalogue()
    models,_,_=candidates(1267,12,0,p,a,'diverse',None,144)
    replay,_,_=candidates(1267,12,0,p,a,'diverse',None,144)
    assert [m.id for m in models]==[m.id for m in replay]
    assert len({m.family for m in models})>=9
    assert len({m.parameters['variation']['aspect'] for m in models})>=2
    assert all(validate(m)['passes'] for m in models)


def test_primary_edge_span_and_ancillary_are_contained():
    p,a=catalogue()
    for i in range(44):
        model=create(1267,i,primary=p,ancillary=a,mode='diverse')
        assert validate(model)['passes']
        f=next(f for f in p+a if f['id']==model.family)
        main=next(c for c in model.components if c.id=='main')
        if f.get('edge_span_axis')=='x':
            assert main.bounds[0]==0.0 and main.bounds[3]==1.0
        if f.get('edge_span_axis')=='y':
            assert main.bounds[1]==0.0 and main.bounds[4]==1.0


def test_pipeline_refill_retains_related_policy():
    with tempfile.TemporaryDirectory() as temp:
        p,_=catalogue()
        out=Path(temp)/'run'
        build(out,seed=1267,designs=4,workers=1,candidate_mode='related',
              industry=p[0]['id'],roof_colours='on',facade_mode='decals')
        data=json.loads((out/'manifest.json').read_text())
        old=next(k for k,v in data['candidates'].items() if v['family']==p[0]['id'])
        vote(out,reject=[old])
        result=refill(out,workers=1)
        new=result['replaced'][old]
        updated=json.loads((out/'manifest.json').read_text())
        assert updated['candidates'][new]['family']==p[0]['id']
        assert updated['candidate_mode']=='related'
        assert updated['roof_colours']=='on'
        assert len(updated['nodes'][updated['candidates'][new]['current']]['sprites'])==4
