"""Negative controls for the golden oracle: damaged metadata must be rejected."""
import pytest
from test_golden_outputs import REFERENCE, assert_complete_sprite_coverage


def simulated_manifest(case):
    nodes = {}
    candidates = {}
    for key in case['meshes']:
        node_id=f'node_{key}'
        candidates[key]={'current':node_id}
        nodes[node_id]={'sprites':[{'rotation':angle} for angle in (0,90,180,270)]}
    return {'nodes':nodes,'candidates':candidates}


@pytest.mark.parametrize('mode',tuple(REFERENCE['cases']))
@pytest.mark.parametrize('damage',('missing','duplicate','unexpected','wrong_candidate'))
def test_golden_rejects_incomplete_or_incorrect_sprite_inventory(mode,damage):
    case=REFERENCE['cases'][mode]
    manifest=simulated_manifest(case)
    key=next(iter(case['meshes']))
    records=manifest['nodes'][f'node_{key}']['sprites']
    assert_complete_sprite_coverage(manifest,case,mode)
    if damage=='missing': records.pop()
    elif damage=='duplicate': records[-1]={'rotation':180}
    elif damage=='unexpected': records[-1]={'rotation':45}
    elif damage=='wrong_candidate': manifest['candidates']['unexpected']={'current':f'node_{key}'}
    with pytest.raises(AssertionError):
        assert_complete_sprite_coverage(manifest,case,mode)
