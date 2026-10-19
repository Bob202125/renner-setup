import importlib.util, tempfile, unittest, subprocess, os, json
from pathlib import Path
spec=importlib.util.spec_from_file_location('backend',Path(__file__).parents[1]/'Sources/backend.py'); b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
class BackendTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name); b.HOME=self.root; b.STATE=self.root/'state'; b.REGISTRY=self.root/'utils/.obsidian_vaults.zsh'
        self.v=self.root/'ObsidianVaults/vault'; (self.v/'.obsidian').mkdir(parents=True)
    def tearDown(self): self.t.cleanup()
    def run_git(self,*args):
        return subprocess.check_output(['/usr/bin/git','-C',str(self.v),*args],stderr=subprocess.DEVNULL).decode()
    def repo(self):
        self.run_git('init','-b','main'); self.run_git('config','user.email','fixture@example.invalid'); self.run_git('config','user.name','Fixture'); (self.v/'note.md').write_text('first'); self.run_git('add','.'); self.run_git('commit','-m','first')
    def test_registry_quotes(self):
        values={'test':str(self.v),"odd_alias":str(self.root/"a ' quote Ω")}
        self.assertEqual(b.parse_registry(b.encode_registry(values).decode()),values)
        with self.assertRaises(ValueError): b.parse_registry('echo hello')
    def test_cas_and_backup(self):
        _,rev=b.registry(); b.replace_registry({'one':str(self.v)},rev)
        with self.assertRaises(ValueError): b.replace_registry({},rev)
        _,rev=b.registry(); b.replace_registry({'two':str(self.v)},rev)
        self.assertEqual(len(list((b.STATE/'backups').glob('*'))),1)
    def test_shortcut_collision(self):
        _,rev=b.registry(); b.replace_registry({'one':str(self.v),'two':'/other'},rev); _,rev=b.registry()
        with self.assertRaises(ValueError): b.shortcut({'alias':'two','path':str(self.v),'registryRevision':rev})
        with self.assertRaises(ValueError): b.shortcut({'alias':'open','path':str(self.v),'registryRevision':rev})
    def test_discovery_dedupe_missing(self):
        _,rev=b.registry(); b.replace_registry({'one':str(self.v),'also':str(self.v),'gone':'/missing/vault'},rev)
        out=b.discover()['vaults']; self.assertEqual(len(out),2); self.assertEqual(len([v for v in out if v['available']]),1)
        self.assertEqual(next(v for v in out if v['available'])['aliases'],['also','one'])
    def test_metadata_stale(self):
        req={'path':str(self.v),'revision':0,'title':'Test','groups':['Physics','Physics'],'favorite':True}; b.update(req)
        self.assertEqual(b.discover()['vaults'][0]['groups'],['Physics'])
        with self.assertRaises(ValueError): b.update(req)
    def test_git_clean_dirty_categories(self):
        self.repo(); self.assertEqual(b.inspect(str(self.v))['state'],'clean')
        (self.v/'note.md').write_text('changed'); (self.v/'new.md').write_text('new')
        (self.v/'.obsidian/workspace.json').write_text('{}')
        h=b.inspect(str(self.v)); self.assertEqual(h['state'],'dirty'); self.assertEqual(h['unstaged'],1); self.assertGreater(h['untracked'],0)
        self.assertEqual(self.run_git('diff','--name-only').strip(),'note.md')
    def test_nested_scope(self):
        self.repo(); (self.v/'docs/.obsidian').mkdir(parents=True); (self.v/'docs/a.md').write_text('a'); self.run_git('add','.'); self.run_git('commit','-m','docs')
        (self.v/'note.md').write_text('outside'); h=b.inspect(str(self.v/'docs')); self.assertTrue(h['nested']); self.assertEqual(h['state'],'clean'); self.assertEqual(h['commitSubject'],'docs')
        (self.v/'docs/a.md').write_text('inside'); self.assertEqual(b.inspect(str(self.v/'docs'))['content'],1)
    def test_ahead_and_behind(self):
        self.repo(); self.run_git('branch','upstream'); self.run_git('branch','--set-upstream-to','upstream'); (self.v/'note.md').write_text('second'); self.run_git('commit','-am','second')
        self.assertEqual(b.inspect(str(self.v))['ahead'],1)
        self.run_git('checkout','upstream'); (self.v/'extra').write_text('extra'); self.run_git('add','.'); self.run_git('commit','-m','other'); self.run_git('checkout','main')
        h=b.inspect(str(self.v)); self.assertEqual((h['ahead'],h['behind']),(1,1))
    def test_conflict(self):
        self.repo(); self.run_git('checkout','-b','other'); (self.v/'note.md').write_text('other'); self.run_git('commit','-am','other'); self.run_git('checkout','main'); (self.v/'note.md').write_text('main'); self.run_git('commit','-am','main')
        subprocess.run(['/usr/bin/git','-C',str(self.v),'merge','other'],capture_output=True)
        h=b.inspect(str(self.v)); self.assertEqual(h['state'],'conflict'); self.assertEqual(h['conflicts'],1)
    def test_malformed_metadata_preserved(self):
        b.STATE.mkdir(); p=b.STATE/'metadata.json'; p.write_text('{bad')
        with self.assertRaises(ValueError): b.discover()
        self.assertEqual(p.read_text(),'{bad')
if __name__=='__main__': unittest.main()
