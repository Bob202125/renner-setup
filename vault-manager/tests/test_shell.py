from pathlib import Path
import unittest,tempfile,subprocess,os,shutil
class ShellTests(unittest.TestCase):
    def test_reload_and_stale_save(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); (home/'utils').mkdir(); registry=home/'utils/.obsidian_vaults.zsh'
            registry.write_text('typeset -g -A OBS_VAULTS=( [first]=/tmp/first )\n')
            helper=home/'utils/helper'; helper.write_text((Path(__file__).parent/'fixtures/obsidian_helpers.zsh').read_text())
            runtime=home/'Applications/Vault Manager.app/Contents/Resources/backend.py'; runtime.parent.mkdir(parents=True); shutil.copy2(Path(__file__).parents[1]/'Sources/backend.py',runtime)
            env={**os.environ,'HOME':d}; env.pop('VM_HOME',None); env.pop('VM_STATE',None)
            script='''source "$HOME/utils/helper"
OBS_VAULTS[second]=/tmp/second
_save_vault_db || exit 10
[[ ${OBS_VAULTS[second]} == /tmp/second ]] || exit 11
print -r -- 'typeset -g -A OBS_VAULTS=( [external]=/tmp/external )' > "$VAULTS_FILE"
_save_vault_db && exit 12
_oo_reload_vault_db
[[ ${OBS_VAULTS[external]} == /tmp/external ]] || exit 13
[[ -z ${OBS_VAULTS[second]} ]] || exit 14
'''
            p=subprocess.run(['/bin/zsh','-fc',script],env=env,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertIn('[external]',registry.read_text())
