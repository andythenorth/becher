"""Regression oracles for the two v0.11 confirmed defects."""
from pathlib import Path
import hashlib
import json
import tempfile
import numpy as np
import pytest
from src import pipeline
from src.palette import load_palette, open_indexed
from src.selection import vote, refill
from src.architectural_renderer import cast
from src.edge_contrast import apply as edges
from src.semantic_colour import apply as semantic
from src.roof_colour import apply as roofs


def test_cache_validates_absent_and_modified_sprites():
    with tempfile.TemporaryDirectory() as tmp:
        out=Path(tmp)/'run'
        params=dict(seed=1267,designs=1,workers=1,edge_contrast='on',roof_colours='on')
        pipeline.build(out,**params)
        assert pipeline.build(out,**params)['cached'] is True
        m=pipeline._load_manifest(out)
        sprite=out/m['nodes'][m['candidates']['0000']['current']]['sprites'][0]['file']
        original=sprite.read_bytes()
        sprite.unlink()
        with pytest.raises(RuntimeError,match='Cached sprite missing'):
            pipeline.build(out,**params)
        sprite.write_bytes(original)
        im=open_indexed(sprite,load_palette())
        where=np.argwhere(im>0)
        y,x=where[len(where)//2]
        im[y,x]=int(im[y,x])+1
        from src.palette import save_indexed
        save_indexed(sprite,im,load_palette())
        with pytest.raises(RuntimeError,match='checksum mismatch'):
            pipeline.build(out,**params)
        sprite.write_bytes(original)
        assert pipeline.build(out,**params)['cached'] is True


def test_refill_matches_selected_render_options_all_four_rotations():
    with tempfile.TemporaryDirectory() as tmp:
        out=Path(tmp)/'run'
        pipeline.build(out,seed=1267,designs=2,workers=1,edge_contrast='on',
                       roof_colours='on',semantic_colour='on',semantic_hues=4)
        vote(out,reject=['0000'])
        result=refill(out,workers=1)
        key=result['replaced']['0000']
        manifest=pipeline._load_manifest(out)
        node=manifest['nodes'][manifest['candidates'][key]['current']]
        model=pipeline.load_scene(out,node['id'])
        palette=load_palette()
        assert len(node['sprites'])==4
        for record in node['sprites']:
            surface,metrics=cast(model,record['rotation'])
            edged,edge_mask=edges(surface,palette)
            recoloured,_=semantic(surface,metrics['primitive_components'],model,palette,
                                  max_hues=4,base_pixels=edged,contrast_mask=edge_mask)
            expected,_=roofs(surface,metrics['primitive_components'],model,palette,
                             enabled=True,base_pixels=recoloured,contrast_mask=edge_mask)
            actual=open_indexed(out/record['file'],palette)
            np.testing.assert_array_equal(actual,expected)
            assert hashlib.sha256(actual.tobytes()).hexdigest()==record['sha256']
