"""Install a narrow reload/CAS patch; never rewrite the vault registry here."""
from pathlib import Path
import shutil,time,subprocess
home=Path.home(); helper=home/'utils/.obsidian_helpers'
s=helper.read_text()
if '# Vault Manager registry coordination v1' in s:
    print('Shell integration already installed.'); raise SystemExit
old='''# Load the DB if it exists
[[ -f $VAULTS_FILE ]] && source "$VAULTS_FILE"
typeset -gA OBS_VAULTS              # ensure global associative array

# Helper to (re)write the DB safely
_save_vault_db () {
  typeset -p OBS_VAULTS >| "$VAULTS_FILE"
}'''
new='''# Vault Manager registry coordination v1
# Refresh at command boundaries; refuse writes from stale registry snapshots.
_vm_registry_helper="$HOME/Applications/Vault Manager.app/Contents/Resources/backend.py"
_vm_python="/opt/homebrew/bin/python3"
_oo_reload_vault_db () {
  typeset -g _oo_registry_revision
  _oo_registry_revision="$(/usr/bin/shasum -a 256 "$VAULTS_FILE" 2>/dev/null)"
  _oo_registry_revision="${_oo_registry_revision%% *}"
  unset OBS_VAULTS
  typeset -gA OBS_VAULTS
  [[ -f "$VAULTS_FILE" ]] && source "$VAULTS_FILE"
}
_oo_reload_vault_db
_save_vault_db () {
  if [[ ! -f "$_vm_registry_helper" ]]; then
    echo "Vault Manager registry helper missing; registry left unchanged."
    return 1
  fi
  typeset -p OBS_VAULTS | "$_vm_python" "$_vm_registry_helper" shell-save "$_oo_registry_revision" || return 1
  _oo_reload_vault_db
}'''
if old not in s: raise SystemExit('Helper differs; no changes made.')
s=s.replace(old,new)
for func in ['_oo_open','_oo_comp','ocreate','orm']:
    needle=func+' () {' if func!='_oo_comp' else '_oo_comp() {'
    if needle not in s: raise SystemExit('Expected function not found: '+func)
    s=s.replace(needle,needle+'\n  _oo_reload_vault_db',1)
s=s.replace('  _save_vault_db\n','  _save_vault_db || return 1\n')
backup=home/'Library/Application Support/VaultManager/backups'/('obsidian_helpers-'+str(time.time_ns()))
backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(helper,backup)
tmp=helper.with_suffix('.vm-new'); tmp.write_text(s)
subprocess.run(['/bin/zsh','-n',str(tmp)],check=True)
tmp.replace(helper)
print('Installed; backup: '+str(backup))
