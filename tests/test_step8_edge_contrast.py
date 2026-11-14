"""v0.9: non-destructive 1x exposed-edge shader and explicit surface roles."""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
from src.architectures import generate
from src.architectural_renderer import cast, save
from src.edge_contrast import apply, edge_mask, visible_roles
from src.geometry import MATERIAL_IDS, SURFACE_ROLES, VisibleSurfaces
from src.palette import load_palette, open_indexed

PALETTE=load_palette()


class EdgeContrastTests(unittest.TestCase):
    def test_all_families_all_rotations_preserve_exact_geometry(self):
        total=0
        for family in range(12):
            model=generate(1267,family)
            for rotation in (0,90,180,270):
                surf,_=cast(model,rotation)
                geom=tuple(x.copy() for x in (surf.material,surf.normal,surf.depth,surf.primitive))
                disabled,off_mask=apply(surf,PALETTE,enabled=False)
                self.assertTrue(np.array_equal(disabled,surf.reference_pixels))
                self.assertFalse(np.any(off_mask))
                enhanced,mask=apply(surf,PALETTE,enabled=True)
                self.assertEqual(enhanced.dtype,np.uint8)
                self.assertTrue(np.array_equal(enhanced!=0,surf.reference_pixels!=0))
                self.assertTrue(np.array_equal((enhanced!=surf.reference_pixels),(mask>0)))
                self.assertTrue(np.all((mask==0)|(mask==255)))
                self.assertTrue(np.array_equal(geom[0],surf.material))
                self.assertTrue(np.array_equal(geom[1],surf.normal))
                self.assertTrue(np.array_equal(geom[2],surf.depth))
                self.assertTrue(np.array_equal(geom[3],surf.primitive))
                self.assertTrue(np.array_equal(surf.role>0,surf.silhouette))
                self.assertTrue(np.all(~(mask>0) | np.isin(surf.role,[SURFACE_ROLES['wall'],SURFACE_ROLES['roof_top'],SURFACE_ROLES['sawtooth_sheet']])))
                self.assertLess(np.count_nonzero(mask),.35*np.count_nonzero(surf.silhouette))
                total+=np.count_nonzero(mask)
        self.assertGreater(total,1000)

    def test_glass_details_foundations_untouched(self):
        surf,_=cast(generate(1267,10),90)
        enhanced,mask=apply(surf,PALETTE)
        protected=np.isin(surf.role,[SURFACE_ROLES['glazing'],SURFACE_ROLES['detail'],
                                     SURFACE_ROLES['foundation'],SURFACE_ROLES['roof_fascia'],
                                     SURFACE_ROLES['roof_underside']])
        self.assertGreater(protected.sum(),50)
        self.assertTrue(np.array_equal(enhanced[protected],surf.reference_pixels[protected]))
        self.assertFalse(np.any(mask[protected]))

    def test_saved_surface_roles_roundtrip(self):
        surf,_=cast(generate(1267,2),90)
        with tempfile.TemporaryDirectory() as t:
            fn=Path(t)/'sprite.png'
            save(surf,fn,buffers=True)
            saved=VisibleSurfaces.read(fn.with_suffix('.npz'))
            self.assertTrue(np.array_equal(saved.role,surf.role))
            self.assertTrue(np.array_equal(apply(saved,PALETTE)[0],apply(surf,PALETTE)[0]))
    def test_repeatable_and_idempotent(self):
        surf,_=cast(generate(1267,0),0)
        one,mask=apply(surf,PALETTE)
        two,mask2=apply(surf,PALETTE)
        self.assertTrue(np.array_equal(one,two))
        self.assertTrue(np.array_equal(mask,mask2))
        thr,other_mask=apply(surf,PALETTE,base_pixels=one)
        self.assertTrue(np.array_equal(one,thr))
        self.assertFalse(np.any(other_mask))

    def test_cli_edges_from_geometry_writes_indexed_files(self):
        surf,_=cast(generate(1267,2),90)
        with tempfile.TemporaryDirectory() as t:
            inp=Path(t)/'base.png'; out=Path(t)/'edge.png'; mask=Path(t)/'edge_mask.png'
            save(surf,inp,buffers=True)
            cmd=[sys.executable,'-m','becher','edges',
                 '--geometry',str(inp.with_suffix('.npz')),
                 '--out',str(out),'--mode','on','--mask',str(mask)]
            subprocess.run(cmd,check=True,capture_output=True,text=True)
            self.assertTrue(np.array_equal(open_indexed(inp,PALETTE),surf.reference_pixels))
            self.assertTrue(np.array_equal(open_indexed(out,PALETTE),apply(surf,PALETTE)[0]))
            from PIL import Image
            with Image.open(mask) as pic:
                self.assertEqual(pic.mode,'L')
                self.assertTrue(np.array_equal(np.asarray(pic),apply(surf,PALETTE)[1]))
            # Prevent accidental modification of an existing artist file.
            again=subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(again.returncode,0)

    def test_rejects_repainting_geometry_silhouette(self):
        surf,_=cast(generate(1267,0),0)
        changed=surf.reference_pixels.copy();changed[0,0]=1
        with self.assertRaises(ValueError):apply(surf,PALETTE,base_pixels=changed)

if __name__=='__main__':unittest.main()

class PipelineEdgeIntegrationTests(unittest.TestCase):
    def test_pipeline_on_off_have_identical_saved_base_and_distinct_pngs(self):
        import json
        from src.pipeline import build
        with tempfile.TemporaryDirectory() as t:
            off=Path(t)/'off';on=Path(t)/'on'
            build(off,seed=1267,designs=1,workers=1,buffers=True,edge_contrast='off',semantic_colour='off')
            build(on,seed=1267,designs=1,workers=1,buffers=True,edge_contrast='on',semantic_colour='off')
            manif_off=json.loads((off/'manifest.json').read_text())
            manif_on=json.loads((on/'manifest.json').read_text())
            self.assertEqual(manif_off['edge_contrast'],'off')
            self.assertEqual(manif_on['edge_contrast'],'on')
            self.assertEqual(manif_off['candidates'],manif_on['candidates'])
            changed=0
            records_off=manif_off['nodes'][manif_off['candidates']['0000']['current']]['sprites']
            records_on=manif_on['nodes'][manif_on['candidates']['0000']['current']]['sprites']
            expected={0,90,180,270}
            def by_rotation(records):
                angles=[int(record['rotation']) for record in records]
                self.assertEqual(len(angles),len(expected),'missing/duplicate sprite records')
                self.assertEqual(set(angles),expected,'wrong rotation coverage')
                return {int(record['rotation']):record for record in records}
            off_by_rotation=by_rotation(records_off)
            on_by_rotation=by_rotation(records_on)
            for angle in sorted(expected):
                a,b=off_by_rotation[angle],on_by_rotation[angle]
                pix_off=open_indexed(off/a['file'],PALETTE)
                pix_on=open_indexed(on/b['file'],PALETTE)
                changed+=np.count_nonzero(pix_off!=pix_on)
                npz_off=VisibleSurfaces.read((off/a['file']).with_suffix('.npz'))
                npz_on=VisibleSurfaces.read((on/b['file']).with_suffix('.npz'))
                self.assertEqual(npz_off.digest(),npz_on.digest())
                self.assertTrue(np.array_equal(npz_off.reference_pixels,pix_off))
                self.assertTrue(np.array_equal(apply(npz_on,PALETTE)[0],pix_on))
            self.assertGreater(changed,20)
            # The same output directory must reject a different edge setting.
            with self.assertRaises(ValueError):
                build(on,seed=1267,designs=1,workers=1,buffers=True,edge_contrast='off')

