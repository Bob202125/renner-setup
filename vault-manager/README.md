# Vault Manager

A native macOS gallery for existing Obsidian vaults. Installed at `~/Applications/Vault Manager.app`. Requires Apple Silicon, macOS 14 or later, and the Python executable recorded in the app's Info.plist (this install: `/opt/homebrew/bin/python3`). It does not need Obsidian running to inspect the library.

## Open it

Run `vault-manager` in a terminal, or search **Vault Manager** in Alfred or Spotlight. The launcher is `~/bin/vault-manager`. Alfred's normal app search works without Powerpack and was tested. The optional `build.noindex/Vault Manager.alfredworkflow` provides the keyword `vaults` for Powerpack users; it is not installed here because Powerpack is unavailable.

## Use the gallery

Click a card to see its homepage. Use its star for Favorites. Research comes first after Favorites, Other comes last. Each vault belongs to exactly one area. The initial grouping follows the curriculum Subject Map with the user's overrides: Thermodynamics is Physics; numbered course vaults and Current Issues 2025 are Courses. Edit details changes the display name, area, description or cover without moving the vault or changing note links. Add existing vault uses a folder picker and requires a `.obsidian` directory. New subject names can be entered in the Area field.

Search filters the loaded collection by title, path, description, area or shortcut without scanning the filesystem. Refresh status performs local background inspection with three workers. Open in Obsidian is an explicit action, separate from viewing the homepage. The app does not establish cross-Mac writing ownership: honor the existing handoff process before opening a vault on a different Mac.

## Terminal shortcuts

Manage shortcut on a homepage adds a shortcut or renames one of that vault's existing shortcuts. Names are checked for collisions and reserved `oo` commands. Changes use an atomic transaction and a backup of the actual `~/utils/.obsidian_vaults.zsh` registry. No vault directories move.

The installed `~/utils/.obsidian_helpers` now reloads the registry before opening, completing, creating or removing mappings and refuses stale saves. **Open a fresh terminal once**, or run `source ~/utils/.obsidian_helpers` in each existing shell to load this change. Old already-loaded shell functions cannot be patched by changing their file. Existing helper commands remain intact.

## Understanding status

Committed means the scoped working tree was clean when checked, not that every commit is pushed. Ahead/behind uses locally cached upstream refs and is not a live remote check. No fetch, commit, pull or push is performed. Content, learning state, configuration and workspace changes are counted separately. Untracked directories may be reported as entries rather than expanded file counts. A staged-and-unstaged file contributes to both stage signals.

Nested vaults (such as calc-manager/docs) show file changes and latest commit scoped to the vault folder; branch and ahead/behind refer to the parent repository. Last content edit uses file modification times, not an audit trail. Metadata scans stop after 40,000 files or a bounded time and visibly report partial results. Ordinary `.obsidian` configuration, caches and symlink directories are excluded; Study Studio learning data is included. Missing folders stay visible. Plugin manifests show installed versions and enabled flags, not a certification of runtime compatibility.

## Files and recovery

Source: `Sources/VaultManager.swift`, `Sources/backend.py`, and the reviewed `Sources/areas.json`. Detailed plan: `PLAN.md`. Organization and status caches are outside vaults in `~/Library/Application Support/VaultManager/`. `metadata.json` has a revision and `metadata.previous.json` retains the previous successful save. `backups/` holds changed shortcut registries, the original terminal helper, and the previous app bundle.

Quit the manager before restoring organization state. Restore a specific reviewed backup, not the whole directory blindly. To remove the shell integration, restore the original `obsidian_helpers-*` backup to `~/utils/.obsidian_helpers` and reload it in open shells. Retain any later unrelated helper edits. The app never deletes, moves or commits a vault.

## Build and test

Run `python3 -m unittest discover -s tests -v`, then `python3 scripts/build.py`. The build uses the installed Swift SDK, ad-hoc signs the local bundle, and creates the icon plus optional Alfred workflow. A build-local VFS overlay works around a duplicate SwiftBridging module map left by this Mac's CLT upgrade; it does not modify the SDK. Build artifacts live in `build.noindex` to prevent duplicate Alfred results. `scripts/install.py` is first-install only and refuses existing targets. Updating an installed app requires quitting it, backing up the bundle, copying the rebuilt bundle, and signing/verifying the result.

No account, network server, telemetry or subscription is involved. Private source repository: `git@github.com:gclopton/vault-manager.git`. See `INSTALL-M1.md` for verified receiving-machine setup. M1 installation is a separate check from publication.
