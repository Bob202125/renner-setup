# Install on Big brother (M1)

This repository contains application source and tests, not M4 vault contents or machine state. Keep M1's existing vault registry, favorites, paths, credentials and active writing ownership. Installing this gallery does not transfer vault ownership. Do not open a vault on both Macs to test it.

## 1. Preflight

Check `sw_vers`, `uname -m`, `swift --version`, `python3 --version`, and GitHub access. This build currently requires macOS 14+ on Apple Silicon and a Swift compiler supporting that SDK. Python uses only the standard library. If macOS/SDK is older, report the version before installing; do not upgrade the operating system as part of this task.

Check whether `~/Projects/vault-manager`, `~/Applications/Vault Manager.app`, and `~/bin/vault-manager` exist. Preserve any existing or unpublished work. Clone only into an absent destination, or fetch and fast-forward an existing clean repository after checking its origin and branch. Never reset or stash to make it clean.

## 2. Receive the exact release

Clone `git@github.com:gclopton/vault-manager.git` into `~/Projects/vault-manager`. Compare `git rev-parse HEAD` with the exact commit provided in the coordination message. Keep the source checkout; it provides build scripts, reviewable code and future updates.

## 3. Test and build

From the repository:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build.py
codesign --verify --deep --strict 'build.noindex/Vault Manager.app'
```

The tests use disposable temporary homes and Git repositories. They do not need M4 files. The shell fixture intentionally models the matching oo helper and uses `/opt/homebrew/bin/python3`; if the M1 interpreter is elsewhere, adapt that path consistently and report the difference. The build records the actual Python executable in Info.plist. Rebuild if it moves. The CLT compatibility overlay is local to the build and never edits system SDK files.

## 4. Install and integrate

Run `python3 scripts/install.py`. It refuses existing app/launcher targets rather than overwriting them. For an update, quit the manager, preserve the previous bundle, and explicitly replace it only after validating the new build. No organization data lives inside the app bundle.

Run `python3 scripts/install_shell.py` only after reviewing the current `~/utils/.obsidian_helpers`. It makes a dated backup, preserves the actual registry, and refuses an unexpected helper layout. If it differs, merge the reload and stale-save behavior deliberately; do not replace M1's whole helper with the test fixture. Use the same installed Python path in `_vm_python`. This optional helper integration is required before treating shortcut management as safe across current shell sessions.

Open new terminal sessions, or run `source ~/utils/.obsidian_helpers` in existing sessions. Ensure `~/bin` is on PATH; add it once if absent. Launch with `vault-manager` or `open "$HOME/Applications/Vault Manager.app"`.

## 5. Verify on M1

Check gallery import against the M1 registry. Missing paths must remain visible, not recreated. Verify Research first after Favorites, Other last, one section per vault, Thermodynamics only in Physics, and numbered course vaults in Courses. Test search, a reversible favorite save/relaunch, a vault homepage, and Git status against a direct read-only Git check. Use a harmless available vault for launch testing; respect active vault handoffs.

Search Vault Manager in Alfred and open the installed `~/Applications` copy. Custom `vaults` keyword workflow is optional and requires Powerpack; normal app search does not. The build stays in `build.noindex` to avoid duplicate search results. Do not buy software or import other preferences for this task.

Report exact received commit, macOS/Swift/Python versions, installed app/launcher paths, tests, UI checks, helper merge differences and unresolved limitations to the coordinating chat. Successful clone/build alone is not installation completion.

## Rollback

Quit the app. Restore a reviewed previous app bundle if replacing an earlier installation. The helper backup is under `~/Library/Application Support/VaultManager/backups/obsidian_helpers-*`; preserve any subsequent unrelated helper edits when reverting. Registry changes have separate backups. Do not delete the registry or any vault. Organization remains under `~/Library/Application Support/VaultManager/` and is host-local; do not copy M4's metadata over M1's.
