"""Step 2 correctness: structural grammars, deterministic mutation and true raycasting."""
from dataclasses import replace
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from src.architectures import library as _library, generate as _generate, Component
from src.architectural_validation import validate
from src.architectural_renderer import cast
from src.palette import load_palette


# Active approved grammar catalogue. Retired catalogues are not test fixtures.
library = _library
generate = _generate

class ArchitectureTests(unittest.TestCase):
    def test_active_data_grammars_and_valid_assembly(self):
        families=library()
        self.assertEqual(len(families),6)
        self.assertEqual(len(set(x['id'] for x in families)),len(families))
        for i in range(len(families)*3):
            model=generate(1267,i)
            self.assertTrue(validate(model)['passes'],(model.family,validate(model)))

    def test_structural_mutation_is_seeded(self):
        a=generate(1267,7)
        b=generate(1267,7)
        c=generate(1268,7)
        self.assertEqual(a,b)
        self.assertNotEqual(a.id,c.id)
        self.assertNotEqual(a.parameters['global_scale'],c.parameters['global_scale'])

    def test_reroll_only_roof_not_building_dimensions(self):
        a=generate(1267,5)
        b=generate(1267,5,rerolls={'roof:main':7})
        orig=[x for x in a.components if x.role=='fabric']
        after=[x for x in b.components if x.role=='fabric']
        self.assertEqual(orig,after)
        self.assertNotEqual([x for x in a.components if x.role=='roof'],
                            [x for x in b.components if x.role=='roof'])

    def test_invalid_detached_annex_is_rejected(self):
        model=generate(1267,2)
        parts=list(model.components)
        annex=next(i for i,x in enumerate(parts) if x.role=='fabric' and x.parent)
        x=parts[annex]
        parts[annex]=replace(x,bounds=(.01,.01,.05,.09,.09,.5))
        bad=replace(model,components=tuple(parts))
        v=validate(bad)
        self.assertFalse(v['passes'])
        self.assertTrue(any('attachment' in x or 'detached' in x for x in v['issues']))

    def test_invalid_roof_and_unsupported_feature_rejected(self):
        model=generate(1267,0)
        parts=list(model.components)
        i=next(i for i,x in enumerate(parts) if x.role=='roof')
        parts[i]=replace(parts[i],roof='arbitrary_bent_foil')
        v=validate(replace(model,components=tuple(parts)))
        self.assertIn(f'{parts[i].id}:unknown_roof',v['issues'])

    def test_mesh_rotations_and_indexed_light(self):
        model=generate(1267,4)
        images=[]
        pal=load_palette()
        for rotation in (0,90,180,270):
            surf,stats=cast(model,rotation)
            self.assertEqual(surf.reference_pixels.shape,(128,64))
            self.assertEqual(surf.reference_pixels.dtype,np.uint8)
            self.assertGreater(stats['visible_primitive_ids'],0)
            self.assertGreater(stats['occupied_pixels'],1200)
            self.assertTrue(surf.validate())
            self.assertTrue((surf.material > 0).any())
            visible=surf.material>0
            self.assertTrue(np.all(np.isfinite(surf.normal[visible])))
            self.assertEqual(np.count_nonzero(surf.reference_pixels==0),
                             np.count_nonzero(surf.material==0))
            images.append(surf.reference_pixels.copy())
        self.assertEqual(len({hashlib.sha256(x.tobytes()).digest() for x in images}),4)

    def test_mutations_do_not_rewrite_nonroof_components(self):
        a=generate(999,14)
        b=generate(999,14,rerolls={'roof:main':10})
        aa=[x for x in a.components if x.role!='roof' and x.role!='monitor']
        bb=[x for x in b.components if x.role!='roof' and x.role!='monitor']
        self.assertEqual(aa,bb)

if __name__=='__main__':unittest.main()
