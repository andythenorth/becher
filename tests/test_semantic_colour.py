"""Artist-handoff semantic recolouring stays deterministic and category-bounded."""
import unittest
import tempfile
from pathlib import Path
import numpy as np
from src.architectures import generate
from src.architectural_renderer import cast
from src.edge_contrast import apply as edge_apply
from src.semantic_colour import (
    apply, assignment, WINDOW_RAMP, DOOR_RAMP, GREEBLE_RAMP,
)
from src.palette import load_palette, open_indexed
from src.pipeline import build
from src.geometry import SURFACE_ROLES


class SemanticColourTests(unittest.TestCase):
    def test_hues_are_bounded_and_stable(self):
        for i in range(24):
            building=generate(1267,i)
            for k in (3,4):
                x=assignment(building,k)
                self.assertEqual(x,assignment(building,k))
                self.assertLessEqual(len(set(x.values())),k)
                self.assertLessEqual(max(x.values(),default=0),k-1)
                self.assertEqual(x['main'],0)

    def test_material_category_ranges_are_respected(self):
        building=generate(1267,0)
        palette=load_palette()
        surf,metrics=cast(building,90)
        edged,mask=edge_apply(surf,palette)
        pix,_=apply(surf,metrics['primitive_components'],building,palette,
                    base_pixels=edged,contrast_mask=mask)
        door_ids=[int(pid) for pid,cid in metrics['primitive_components'].items()
                  if any(tok in cid.lower() for tok in ('door','lintel','jamb','header'))]
        door_pixels=np.isin(surf.primitive,door_ids) & (
            (surf.role==SURFACE_ROLES['glazing']) | (surf.role==SURFACE_ROLES['detail'])
        )
        window_pixels=(surf.role==SURFACE_ROLES['glazing']) & (~door_pixels)
        detail_pixels=(surf.role==SURFACE_ROLES['detail']) & (~door_pixels)
        self.assertTrue(np.all(np.isin(pix[window_pixels], WINDOW_RAMP)))
        if np.any(door_pixels):
            self.assertTrue(np.all(np.isin(pix[door_pixels], DOOR_RAMP)))
        if np.any(detail_pixels):
            self.assertTrue(np.all(np.isin(pix[detail_pixels], GREEBLE_RAMP)))
        self.assertGreater(int(np.count_nonzero(pix!=edged)),0)
        # Ground tile replacement uses the requested flat grey index.
        self.assertGreater(int(np.count_nonzero(pix==10)),0)

    def test_default_on_and_disabling_matches_original_shaded_pixels(self):
        with tempfile.TemporaryDirectory() as folder:
            a=Path(folder)/'default'; b=Path(folder)/'off'
            build(a,seed=1267,designs=1,workers=1,buffers=True)
            build(b,seed=1267,designs=1,workers=1,buffers=True,semantic_colour='off')
            import json
            man_a=json.loads((a/'manifest.json').read_text())
            man_b=json.loads((b/'manifest.json').read_text())
            self.assertEqual(man_a['semantic_colour'],'on')
            self.assertEqual(man_b['semantic_colour'],'off')
            entry_a=man_a['nodes'][man_a['candidates']['0000']['current']]['sprites']
            entry_b=man_b['nodes'][man_b['candidates']['0000']['current']]['sprites']
            from src.geometry import VisibleSurfaces
            for x,y in zip(entry_a,entry_b):
                px=open_indexed(a/x['file'],load_palette())
                py=open_indexed(b/y['file'],load_palette())
                aa=VisibleSurfaces.read((a/x['file']).with_suffix('.npz'))
                bb=VisibleSurfaces.read((b/y['file']).with_suffix('.npz'))
                self.assertEqual(aa.digest(),bb.digest())
                np.testing.assert_array_equal(py,bb.reference_pixels)
                self.assertGreater(int(np.count_nonzero(px!=py)),0)
            with self.assertRaises(ValueError):
                build(a,seed=1267,designs=1,workers=1,semantic_colour='off')


if __name__=='__main__':
    unittest.main()
