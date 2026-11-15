"""Rejected wall-streak generators must not return in new candidate builds."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import numpy as np
from src.architectures import generate as _generate, library as _library
from src.mesh.render import cast
from src.feature_passes import build_features, STAGES, is_feature, reroll
from src.pipeline import build, load_scene, _load_manifest
from src.palette import load_palette

FORBIDDEN = ('/rib/', '/column/', '/downpipe/', '/elbow/', ':rib_', '/jamb_a', '/jamb_b', '/sill/')


generate = _generate

class WallArtifactRemovalTests(unittest.TestCase):
    def test_generators_removed_not_suppressed(self):
        self.assertEqual(STAGES, ('windows','doors','equipment','greeble'))
        for i in range(6):
            root=generate(1267,i)
            model=build_features(root)
            labels=[c.id for c in model.components]
            self.assertFalse(any(part in label for label in labels for part in FORBIDDEN))
            self.assertFalse(any(is_feature(c,'frames') or is_feature(c,'pipes') for c in model.components))
            if i == 0:  # approved hall contains all feature stages
                for stage in STAGES:
                    self.assertTrue(any(is_feature(c,stage) for c in model.components))
            for c in model.components:
                if c.role=='roof':self.assertTrue(c.rise >= 0)
                # The removed class of wall artefact is a tall, slender frame.
                if is_feature(c, 'doors') and c.material=='frame':
                    x0,y0,z0,x1,y1,z1=c.bounds
                    self.assertLess(z1-z0, .08, c.id)

    def test_wall_features_removed_with_rerolls(self):
        root=generate(1267,5)
        model=build_features(root)
        for stage in STAGES:
            model=reroll(model,stage,counter=3)
            self.assertFalse(any(part in c.id for c in model.components for part in FORBIDDEN))
        with self.assertRaises(ValueError):reroll(model,'frames')
        with self.assertRaises(ValueError):reroll(model,'pipes')

    def test_pipeline_generated_scene_and_indexed_output(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)/'run'
            build(run,designs=2,workers=1,buffers=False)
            m=_load_manifest(run)
            self.assertEqual(m['stages'],list(STAGES))
            self.assertNotIn('wall_details',m)
            for candidate in m['candidates'].values():
                self.assertEqual(len(candidate['history']),5)
                model=load_scene(run,candidate['current'])
                self.assertFalse(any(part in c.id for c in model.components for part in FORBIDDEN))
                for item in m['nodes'][candidate['current']]['sprites']:
                    with Image.open(run/item['file']) as im:
                        self.assertEqual(im.mode,'P')
                        self.assertEqual(im.size,(64,128))
                        self.assertEqual(im.getpalette(),load_palette())
            self.assertTrue(build(run,designs=2,workers=1,buffers=False)['cached'])
            # An older compiled run must never be reused after a source fix.
            import json
            manifest_path=run/'manifest.json'
            historic=json.loads(manifest_path.read_text())
            historic.pop('pipeline_revision')
            manifest_path.write_text(json.dumps(historic))
            with self.assertRaisesRegex(ValueError,'different Becher revision'):
                build(run,designs=2,workers=1,buffers=False)

if __name__=='__main__':unittest.main()
