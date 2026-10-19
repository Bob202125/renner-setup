from pathlib import Path
import shutil,subprocess
root=Path(__file__).resolve().parents[1]; home=Path.home(); source=root/'build.noindex/Vault Manager.app'; dest=home/'Applications/Vault Manager.app'
dest.parent.mkdir(exist_ok=True)
if dest.exists(): raise SystemExit('App already installed. Quit it and use an explicit update; no replacement performed.')
launcher=home/'bin/vault-manager'; launcher.parent.mkdir(exist_ok=True)
if launcher.exists(): raise SystemExit('Existing vault-manager command preserved; inspect before updating.')
shutil.copytree(source,dest)
launcher.write_text('#!/bin/sh\nexec /usr/bin/open "$HOME/Applications/Vault Manager.app" "$@"\n'); launcher.chmod(0o755)
subprocess.run(['/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister','-f',str(dest)],check=True)
print(dest); print(launcher)
