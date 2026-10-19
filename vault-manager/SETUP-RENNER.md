# Vault Manager for Renner

This folder contains the complete tracked source from Grady's Vault Manager commit `8972ed8305b8e8fded0b08e65d7115e02118181e`, including the native Swift interface, Python backend, build/install scripts and tests. The original README and INSTALL-M1 describe Grady's installation; use this document for Renner's setup.

Ask Codex to install from this folder on Renner's Mac. The current build targets Apple Silicon and macOS 14 or later. Check those requirements, Python 3 and Apple's command-line developer tools (`swiftc`) first. The build records the Python executable found on this machine, so build on Renner's Mac.

Install or merge the parent repository's utilities first using START-HERE.md. Preserve any existing vault registry and settings. From this folder run:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build.py
codesign --verify --deep --strict 'build.noindex/Vault Manager.app'
python3 scripts/install.py
open "$HOME/Applications/Vault Manager.app"
```

The installer refuses an existing app or ~/bin/vault-manager launcher. If either exists, inspect and back it up before deliberately updating; do not delete existing state. Add ~/bin to PATH if needed for the vault-manager command. Do not run scripts/install_shell.py for this bundle: its portable Obsidian helpers already include registry coordination and use ~/utils/lib/vault_registry_backend.py.

The gallery reads Renner's own ~/utils/.obsidian_vaults.zsh and keeps its metadata under ~/Library/Application Support/VaultManager. No Grady registry, notes or gallery metadata are included. Sources/areas.json contains initial subject-name grouping rules; unmatched vaults default to Other and can be organized in the app.

Verify the installed app launches, lists Renner's vaults, opens a selected vault in Obsidian, and shares shortcut changes correctly with a fresh terminal. Test a disposable vault before changing established shortcuts. Local source tests passed on Grady's Mac; recipient installation and native UI verification must still be performed. The optional Alfred workflow requires Powerpack; normal app launch does not.
