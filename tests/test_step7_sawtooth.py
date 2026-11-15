"""True volumetric sawtooth sections and 1x ray visibility invariants."""
from pathlib import Path

import hashlib
import unittest
import numpy as np
from src.architectures import generate as _generate, library as _library
from src.mesh.render import cast
from src.geometry import MATERIAL_IDS



# Current approved sawtooth family: multi_slope_industrial_hall.
generate = _generate

class SawtoothRayTests(unittest.TestCase):
    def test_clerestory_pixels_are_exposed_by_depth_test(self):
        for index in (3,9):
            model=generate(1267,index)
            for rotation in (0,90,180,270):
                surface,report=cast(model,rotation)
                self.assertTrue(any('sheet:' in name for name in report['visible_components']))
                seen=sum(count for name,count in report['visible_components'].items()
                         if ':clerestory:' in name)
                if index == 3:  # this seed exposes the clerestory in every view
                    self.assertGreater(seen,0,(index,rotation))
                if index == 3 and rotation in (90,180):
                    self.assertGreater(seen,40,(index,rotation))
                    self.assertGreater(np.count_nonzero(surface.material==MATERIAL_IDS['glass']),40)

    def test_sawtooth_render_is_deterministic(self):
        # This checks deterministic mesh rendering, not retired legacy geometry.
        for index in (3,9):
            model=generate(1267,index)
            for rotation in (0,90,180,270):
                a,ma=cast(model,rotation)
                b,mb=cast(model,rotation)
                self.assertEqual(a.digest(),b.digest())
                self.assertEqual(ma['visible_components'],mb['visible_components'])

    def test_thin_sheets_have_correct_plane_normal(self):
        for index in (3,9):
            model=generate(1267,index)
            for rotation in (0,90,180,270):
                surface,report=cast(model,rotation)
                owners={int(pid):name for pid,name in report['primitive_components'].items()
                        if ':sheet:' in name}
                self.assertEqual(len(owners),next(c.count for c in model.components if c.roof=='sawtooth'))
                hit=np.isin(surface.primitive,list(owners))
                self.assertGreater(np.count_nonzero(hit),30)
                # The upper surface of a sloping sheet must have a vertical normal component.
                top=hit&(surface.normal[...,2]>.1)
                self.assertGreater(np.count_nonzero(top),0)
                self.assertTrue(np.all(np.isfinite(surface.depth[hit])))
                self.assertTrue(np.all(surface.material[hit]==MATERIAL_IDS['roof']))

if __name__=='__main__': unittest.main()
