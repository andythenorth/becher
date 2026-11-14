"""Step 4: source scene geometry must survive every colour/paint branch."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from src.handoff import prepare, grade, _light_bands, _zones
from src.geometry import VisibleSurfaces
from src.palette import load_palette, open_indexed
from src.paint import apply_rgba
from src.pipeline import build


class Step4HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.run_dir = cls.root / 'run'
        cls.out = cls.root / 'handoff'
        build(cls.run_dir, seed=1267, designs=2, workers=1, buffers=True)
        prepare(cls.run_dir,cls.out,['0000'])
        cls.view = cls.out / 'candidate_0000' / 'r000'

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_four_views_and_valid_palette(self):
        palette = load_palette()
        for angle in (0,90,180,270):
            view = self.out / 'candidate_0000' / f'r{angle:03d}'
            surface=VisibleSurfaces.read(view/'geometry.npz')
            base=open_indexed(view/'shaded_original.png',palette)
            np.testing.assert_array_equal(base,surface.reference_pixels)
            self.assertEqual(base.dtype,np.uint8)
            self.assertEqual(base.shape,(128,64))
            self.assertTrue((view/'primitive_map.json').is_file())
            self.assertTrue((view/'artist_rgba.png').is_file())
            self.assertTrue((view/'open_in_photoshop.jsx').is_file())

    def test_colour_branches_do_not_change_silhouette(self):
        surface=VisibleSurfaces.read(self.view/'geometry.npz')
        manifest=json.loads((self.out/'manifest.json').read_text())
        ident=manifest['candidates']['0000']['views']['000']['treatment']
        folder=self.view/'treatments'/ident
        base=open_indexed(self.view/'shaded_original.png',load_palette())
        brick=open_indexed(folder/'brick_concrete.png',load_palette())
        steel=open_indexed(folder/'painted_steel.png',load_palette())
        self.assertTrue(np.array_equal(base!=0,brick!=0))
        self.assertGreater(int(np.count_nonzero(brick!=steel)),30)
        self.assertTrue((folder/'lighting.png').is_file())

    def test_semantic_masks_partition_all_pixels(self):
        surface=VisibleSurfaces.read(self.view/'geometry.npz')
        meta=json.loads((self.view/'primitive_map.json').read_text())
        masks=_zones(surface,meta)
        self.assertGreater(np.count_nonzero(masks['main_wall']),0)
        self.assertGreater(np.count_nonzero(masks['roof']),0)
        self.assertTrue(np.array_equal(sum(m.astype('uint8') for m in masks.values()),
                                       surface.silhouette.astype('uint8')))
        for key,mask in masks.items():
            image=np.asarray(Image.open(self.view/'masks'/f'{key}.png'))
            self.assertTrue(np.array_equal(image>0,mask))

    def test_grade_cannot_ray_cast_and_is_repeatable(self):
        source_digest=VisibleSurfaces.read(self.view/'geometry.npz').digest()
        blank_bytes=(self.view/'artist_rgba.png').read_bytes()
        with patch('src.handoff.cast',side_effect=AssertionError('grade invoked raycast')):
            result=grade(self.out,candidate='0000',name='test',light=(1.,.4,.6),
                         profile_names=('brick_concrete',))
            second=grade(self.out,candidate='0000',name='test',light=(1.,.4,.6),
                         profile_names=('brick_concrete',))
        self.assertEqual(result,second)
        self.assertEqual(VisibleSurfaces.read(self.view/'geometry.npz').digest(),source_digest)
        self.assertEqual((self.view/'artist_rgba.png').read_bytes(),blank_bytes)

    def test_different_lighting_changes_shading_not_geometry(self):
        surface=VisibleSurfaces.read(self.view/'geometry.npz')
        a=_light_bands(surface,(.94,.64,.23))
        b=_light_bands(surface,(-.94,-.64,.23))
        self.assertFalse(np.array_equal(a[surface.silhouette],b[surface.silhouette]))
        np.testing.assert_array_equal(a[~surface.silhouette],0)
        with self.assertRaises(ValueError):
            _light_bands(surface,(0,0,0))

    def test_rgba_artist_overlay_import(self):
        surface=VisibleSurfaces.read(self.view/'geometry.npz')
        source=surface.reference_pixels
        palette=load_palette()
        y,x=np.argwhere(surface.silhouette)[0]
        art=np.zeros((128,64,4),dtype=np.uint8)
        art[y,x,:3]=np.asarray(palette).reshape(256,3)[15]
        art[y,x,3]=255
        path=self.root/'art.png'
        Image.fromarray(art).save(path)
        result=apply_rgba(surface,source,path,palette,exact=True)
        self.assertEqual(int(result[y,x]),15)
        self.assertTrue(np.array_equal(result!=0,source!=0))
        art[y,x,3]=128
        Image.fromarray(art).save(path)
        with self.assertRaises(ValueError):
            apply_rgba(surface,source,path,palette)

    def test_importing_outside_geometry_is_rejected(self):
        surface=VisibleSurfaces.read(self.view/'geometry.npz')
        y,x=np.argwhere(~surface.silhouette)[0]
        art=np.zeros((128,64,4),dtype=np.uint8)
        art[y,x]=[255,0,0,255]
        path=self.root/'outside.png'
        Image.fromarray(art).save(path)
        with self.assertRaises(ValueError):
            apply_rgba(surface,surface.reference_pixels,path,load_palette())

    def test_hand_off_re_run_is_idempotent(self):
        manifest_before=(self.out/'manifest.json').read_bytes()
        art_before=(self.view/'artist_layer.png').read_bytes()
        prepare(self.run_dir,self.out,['0000'])
        self.assertEqual((self.out/'manifest.json').read_bytes(),manifest_before)
        self.assertEqual((self.view/'artist_layer.png').read_bytes(),art_before)

    def test_candidate_append_preserves_existing_artwork(self):
        artist=self.view/'artist_rgba.png'
        before=artist.read_bytes()
        first=json.loads((self.out/'manifest.json').read_text())['candidates']['0000']
        prepare(self.run_dir,self.out,['0001'])
        after=json.loads((self.out/'manifest.json').read_text())
        self.assertEqual(after['candidates']['0000'],first)
        self.assertIn('0001',after['candidates'])
        self.assertEqual(artist.read_bytes(),before)

    def test_seed_reference_scene_not_modified(self):
        original=json.loads((self.run_dir/'manifest.json').read_text())
        scene_path=self.run_dir/original['nodes'][original['candidates']['0000']['current']]['scene']
        text_before=scene_path.read_bytes()
        grade(self.out,candidate='0000',name='other',light=(0.2,.9,.4))
        self.assertEqual(scene_path.read_bytes(),text_before)


if __name__=='__main__':
    unittest.main()
