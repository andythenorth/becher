"""Step 5: no destructive changes to architecture or existing art."""
import shutil
import hashlib
import json
import tempfile
import subprocess
import sys
import os
import unittest
from pathlib import Path
from PIL import Image

from src.palette import load_palette
from src import pipeline
from src.selection import evaluate, vote, refill, export_selection


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.run_dir = Path(cls.tmp.name) / 'run'
        pipeline.build(cls.run_dir, seed=1267, designs=3, workers=1, buffers=True)

        # Prepare a second *immutable* starting state for workflows that need
        # one accepted candidate and one archived/replaced candidate. No test
        # depends on another test having run beforehand.
        cls.post_dir = Path(cls.tmp.name) / 'post_refill_template'
        shutil.copytree(cls.run_dir, cls.post_dir)
        vote(cls.post_dir, accept=['0000'], reject=['0001'])
        refill(cls.post_dir, workers=1, buffers=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        # Every test mutates only its own directory. Tests 04–07 explicitly
        # start from the already-voted/refilled fixture, not ordered side effects.
        base=self.post_dir if self._testMethodName.startswith(('test_04','test_05','test_06','test_07')) else self.run_dir
        self.workspace=Path(self.tmp.name)/self._testMethodName
        shutil.copytree(base,self.workspace)
        self.run_dir=self.workspace

    def test_01_assess_repeatable_non_destructive(self):
        before = (self.run_dir/'manifest.json').read_bytes()
        a = evaluate(self.run_dir, save=False)
        b = evaluate(self.run_dir, save=False)
        self.assertEqual(a, b)
        self.assertEqual(a['summary']['active'], 3)
        self.assertEqual(a['summary']['hard_failures'], 0)
        self.assertEqual(before, (self.run_dir/'manifest.json').read_bytes())
        self.assertEqual(a['candidates']['0000']['pixels_by_rotation'][0] > 250, True)
        evaluate(self.run_dir)
        one = (self.run_dir/'evaluation.json').read_bytes()
        evaluate(self.run_dir)
        self.assertEqual(one, (self.run_dir/'evaluation.json').read_bytes())

    def test_02_vote_preflight(self):
        with self.assertRaisesRegex(ValueError, 'multiple votes'):
            vote(self.run_dir,accept=['0000'],reject=['0000'])
        with self.assertRaisesRegex(ValueError, 'Unknown candidates'):
            vote(self.run_dir,accept=['0000','9090'])
        self.assertEqual(pipeline.read_feedback(self.run_dir)['candidates'], {})

    def test_03_vote_refill_retain_art_and_repeatability(self):
        manifest = pipeline._load_manifest(self.run_dir)
        original = manifest['candidates']['0001']
        node = original['current']
        source = self.run_dir/'nodes'/node/'r000.png'
        original_bytes = source.read_bytes()
        original_scene = (self.run_dir/'nodes'/node/'scene.json').read_bytes()
        vote(self.run_dir,accept=['0000'],reject=['0001'])
        a = refill(self.run_dir,dry_run=True)
        self.assertEqual(a['rejected_active'],['0001'])
        self.assertFalse(a['replaced'])
        result = refill(self.run_dir,workers=1,buffers=True)
        self.assertEqual(len(result['replaced']), 1)
        newkey = result['replaced']['0001']
        self.assertNotEqual(newkey,'0001')
        m = pipeline._load_manifest(self.run_dir)
        self.assertFalse(m['candidates']['0001']['active'])
        self.assertEqual(m['candidates']['0001']['replaced_by'],newkey)
        self.assertEqual(m['candidates'][newkey]['family'],original['family'])
        self.assertEqual(m['candidates'][newkey]['replacement_for'],'0001')
        self.assertEqual(len(m['candidates'][newkey]['history']),5)
        self.assertEqual(len(m['nodes'][m['candidates'][newkey]['current']]['sprites']),4)
        self.assertEqual(original_bytes,source.read_bytes())
        self.assertEqual(original_scene,(self.run_dir/'nodes'/node/'scene.json').read_bytes())
        self.assertEqual(m['candidates']['0000']['current'],manifest['candidates']['0000']['current'])
        self.assertEqual(pipeline.read_feedback(self.run_dir)['candidates']['0000']['vote'],'yes')
        pre = (self.run_dir/'manifest.json').read_bytes()
        repeat = refill(self.run_dir,workers=1)
        self.assertFalse(repeat['replaced'])
        self.assertEqual(pre,(self.run_dir/'manifest.json').read_bytes())

    def test_04_export_accepted_and_native_palette(self):
        out=self.workspace.with_name(self.workspace.name+'_approved')
        summary=export_selection(self.run_dir,out,mode='approved',buffers=True)
        self.assertEqual(summary['selected_designs'],1)
        self.assertEqual(summary['sprites'],4)
        for f in sorted((out/'sprites').glob('*.png')):
            with Image.open(f) as im:
                self.assertEqual(im.mode,'P')
                self.assertEqual(im.size,(64,128))
                self.assertEqual(bytes(im.getpalette()),bytes(load_palette()))
            self.assertTrue(f.with_suffix('.npz').exists())
        self.assertEqual(summary,export_selection(self.run_dir,out,mode='approved',buffers=True))
        with self.assertRaisesRegex(FileExistsError,'Export manifest differs'):
            export_selection(self.run_dir,out,mode='active')

    def test_05_archived_missing_from_active_evaluation_and_export(self):
        report = evaluate(self.run_dir,save=False)
        self.assertEqual(report['summary']['active'],3)
        self.assertEqual(report['summary']['archived'],1)
        self.assertEqual(report['candidates']['0001']['status'],'archived')
        s=export_selection(self.run_dir,self.workspace.with_name(self.workspace.name+'_active'),mode='active')
        self.assertEqual(s['selected_designs'],3)
        self.assertEqual(s['sprites'],12)

    def test_06_palette_mismatch_is_hard_failure(self):
        m = pipeline._load_manifest(self.run_dir)
        node=m['nodes'][m['candidates']['0002']['current']]
        file=self.run_dir/node['sprites'][0]['file']
        original=file.read_bytes()
        try:
            with Image.open(file) as im:
                im.load(); p=im.copy()
            colors=p.getpalette()
            colors[3:6]=[0,0,0]
            p.putpalette(colors)
            p.save(file)
            result=evaluate(self.run_dir,save=False)
            self.assertIn('r0:palette_mismatch',result['candidates']['0002']['hard_failures'])
        finally:
            file.write_bytes(original)
        self.assertFalse(evaluate(self.run_dir,save=False)['candidates']['0002']['hard_failures'])

    def test_07_approved_only_cli_handoff(self):
        from src import __file__ as module_file
        root=Path(module_file).parent.parent
        env=os.environ.copy()
        env['PYTHONPATH']=str(root)
        target=self.workspace.with_name(self.workspace.name+'_approved_handoff_cli')
        cmd=[sys.executable,'-m','becher','handoff','--run',str(self.run_dir),
             '--out',str(target),'--approved-only','--profile','painted_steel']
        proc=subprocess.run(cmd,check=True,env=env,text=True,capture_output=True)
        result=json.loads(proc.stdout)
        self.assertEqual(result['candidates'],1)
        self.assertEqual(result['sprites'],4)
        self.assertEqual(list(json.loads((target/'manifest.json').read_text())['candidates']),['0000'])


if __name__ == '__main__':unittest.main()
