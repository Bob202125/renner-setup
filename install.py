#!/usr/bin/env python3
"""Install into the current user's home; never overwrite an existing utils folder."""
import hashlib,json,shutil,sys
from pathlib import Path
root=Path(__file__).resolve().parent
for rel,expected in json.loads((root/'SHA256.json').read_text()).items():
 if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=expected:
  raise SystemExit('Checksum mismatch: '+rel)
if sys.platform!='darwin':raise SystemExit('This installer is for macOS.')
if not Path('/Applications/Obsidian.app').exists():raise SystemExit('Install Obsidian in /Applications first.')
if not shutil.which('rsync'):raise SystemExit('rsync is required.')
dst=Path.home()/'utils'
if dst.exists():raise SystemExit('~/utils already exists. Ask Codex to review and merge; nothing overwritten.')
shutil.copytree(root/'utils',dst)
rc=Path.home()/'.zshrc';old=rc.read_text() if rc.exists() else ''
line='[[ -f "$HOME/utils/renner-shell.zsh" ]] && source "$HOME/utils/renner-shell.zsh"'
if line not in old:
 if rc.exists():
  import datetime
  backup=rc.with_name('.zshrc.before-renner-setup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
  shutil.copy2(rc,backup)
 rc.write_text(old+'\n# Renner utilities and Obsidian helpers\n'+line+'\n')
print('Installed. Open a new Terminal and run: ocreate renner_notes')
print('No vault was created and no app was launched by this installer.')
