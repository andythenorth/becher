"""Step 3 integrity: stage independence, immutable DAG, genuine indexed output."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import numpy as np

from dataclasses import replace
from src.architectures import generate, library
from src.mesh.render import cast
from src.architectural_validation import validate
from src.feature_passes import STAGES,build_features,is_feature,reroll,validate_features
from src.pipeline import (build,branch,select,load_scene,read_feedback,
                             feedback_action,_load_manifest)
from src.palette import load_palette

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.base=generate(1267,0)
        self.model=build_features(self.base)

    def test_four_independent_passes(self):
        self.assertEqual(len(STAGES),4)
        self.assertTrue(validate(self.model)['passes'])
        self.assertTrue(validate_features(self.model)['passes'])
        self.assertTrue(all(any(is_feature(c,stage) for c in self.model.components)
                            for stage in STAGES))

    def test_fabric_is_untouched(self):
        fabric=[c for c in self.base.components]
        self.assertEqual(fabric,[c for c in self.model.components if not is_feature(c)])
        for stage in STAGES:
            child=reroll(self.model,stage,1)
            self.assertEqual(fabric,[c for c in child.components if not is_feature(c)])
            self.assertTrue(validate_features(child)['passes'])
            # Every other stage preserved as an identical collection of primitives.
            for other in STAGES:
                if other!=stage:
                    self.assertEqual([c for c in self.model.components if is_feature(c,other)],
                                     [c for c in child.components if is_feature(c,other)])

    def test_seeded_repeatability(self):
        self.assertEqual(self.model.to_dict(),build_features(generate(1267,0)).to_dict())
        child=reroll(self.model,'windows')
        self.assertEqual(child.to_dict(),reroll(self.model,'windows').to_dict())
        self.assertEqual(child.parameters['feature_counters']['windows'], self.model.parameters['feature_counters']['windows'] + 1)
        self.assertEqual(child.id,build_features(self.base,{'windows':1}).id)

    def test_invalid_detached_feature_rejected(self):
        source=next(c for c in self.model.components if is_feature(c,'windows'))
        bad=replace(source,bounds=(.4,.4,.1,.45,.46,.2))
        model=replace(self.model,components=tuple(bad if c.id==source.id else c
                                                   for c in self.model.components))
        verdict=validate_features(model)
        self.assertFalse(verdict['passes'])
        self.assertTrue(any('not_on_external_wall' in s for s in verdict['issues']))

    def test_locked_reroll_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'locked'):
            reroll(self.model,'doors',locked=['doors'])

    def test_mesh_render_and_palette(self):
        surf,stats=cast(self.model,90)
        self.assertGreater(stats['occupied_pixels'],700)
        self.assertEqual(surf.reference_pixels.shape,(128,64))
        self.assertEqual(surf.primitive.shape,(128,64))
        self.assertTrue(set(np.unique(surf.material)) <= set(range(8)))

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.out=Path(self.temp.name)/'output'
        self.metrics=build(self.out,designs=2,workers=1,buffers=True)

    def tearDown(self):self.temp.cleanup()

    def test_four_real_rotations_and_npz(self):
        manifest=_load_manifest(self.out)
        self.assertEqual(len(manifest['candidates']),2)
        for key,info in manifest['candidates'].items():
            sprites=manifest['nodes'][info['current']]['sprites']
            self.assertEqual([r['rotation'] for r in sprites],[0,90,180,270])
            for rec in sprites:
                path=self.out/rec['file']
                self.assertTrue(path.exists())
                self.assertTrue(path.with_suffix('.npz').exists())
                with Image.open(path) as im:
                    self.assertEqual(im.mode,'P')
                    self.assertEqual(im.size,(64,128))
                    self.assertEqual(bytes(im.getpalette()),bytes(load_palette()))
                    self.assertEqual(hashlib.sha256(im.tobytes()).hexdigest(),rec['sha256'])

    def test_persistent_lineage_and_select(self):
        manifest=_load_manifest(self.out)
        info=manifest['candidates']['0000']
        self.assertEqual(len(info['history']),5)  # root + 4 independent passes
        parent=info['current'];parent_model=load_scene(self.out,parent)
        orig=[c for c in parent_model.components if not is_feature(c)]
        new=branch(self.out,'0000','windows',counter=2,workers=1)
        self.assertNotEqual(new['id'],parent)
        self.assertEqual(new['parent'],parent)
        new_model=load_scene(self.out,new['id'])
        self.assertEqual(orig,[c for c in new_model.components if not is_feature(c)])
        self.assertEqual(len(new['sprites']),4)
        # Old raster and scene files remain unchanged.
        self.assertTrue((self.out/'nodes'/parent/'r000.png').exists())
        self.assertEqual(load_scene(self.out,parent),parent_model)
        selected=select(self.out,'0000',parent)
        self.assertEqual(selected['id'],parent)

    def test_reviews_locks_and_rejections(self):
        feedback_action(self.out,'0000','vote',value='yes')
        feedback_action(self.out,'0000','lock',value='doors')
        feedback_action(self.out,'0000','notes',notes='Strong silhouette')
        review=read_feedback(self.out)['candidates']['0000']
        self.assertEqual(review['vote'],'yes')
        self.assertIn('doors',review['locks'])
        with self.assertRaisesRegex(ValueError,'locked'):
            branch(self.out,'0000','doors')
        branch(self.out,'0000','windows')
        self.assertEqual(read_feedback(self.out)['candidates']['0000'],review)
        feedback_action(self.out,'0000','unlock',value='doors')
        self.assertNotIn('doors',read_feedback(self.out)['candidates']['0000']['locks'])

    def test_deterministic_reroll(self):
        n1=branch(self.out,'0000','greeble',counter=8)
        select(self.out,'0000',n1['parent'])
        n2=branch(self.out,'0000','greeble',counter=8)
        self.assertEqual(n1['id'],n2['id'])
        a=_load_manifest(self.out)
        self.assertEqual(a['nodes'][n1['id']]['sprites'],a['nodes'][n2['id']]['sprites'])

    def test_rebuild_is_idempotent_preserves_feedback(self):
        feedback_action(self.out,'0000','vote',value='yes')
        before=(self.out/'manifest.json').read_bytes()
        result=build(self.out,designs=2,workers=1,buffers=True)
        self.assertTrue(result['cached'])
        self.assertEqual(before,(self.out/'manifest.json').read_bytes())
        self.assertEqual(read_feedback(self.out)['candidates']['0000']['vote'],'yes')
        with self.assertRaisesRegex(ValueError,'different run'):
            build(self.out,seed=1268,designs=2,workers=1)

    def test_not_valid_candidate_key(self):
        with self.assertRaisesRegex(ValueError,'Unknown candidate'):
            branch(self.out,'9999','doors')

if __name__=='__main__':unittest.main()
