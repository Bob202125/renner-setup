# Vault Manager implementation plan

## Outcome and boundaries

Build a standalone native macOS gallery for the user's existing Obsidian vaults. Favorites appear first, Research is the first subject area, Other is last; searchable subject sections lead to a vault homepage. Provide clear Git/content activity, editable organization and `oo` shortcuts, installed plugin information, Finder/Obsidian launch, terminal launch, Alfred/Spotlight discovery, and a custom icon. Existing vault contents, research files, credentials and practice history are not rewritten. No automatic commit, fetch, pull, plugin upgrade, vault deletion or writing-ownership transfer.

## Architecture decision

Use SwiftUI/AppKit for a native macOS 14+ application, with a bundled Python standard-library backend. Swift is already installed; this avoids provisioning Rust and a web frontend for a Mac-only tool. Python is found explicitly at build/install time and checked at launch. All subprocess arguments are arrays, never shell strings. The backend owns registry parsing, transactional metadata and bounded Git/filesystem inspection. UI work stays on the main thread, inspection off it. Package into `~/Applications/Vault Manager.app`; provide `vault-manager` executable in `~/bin` and an Alfred workflow as a fallback to ordinary app search.

## Stage 1 — Registry and data model

Read the existing `~/utils/.obsidian_vaults.zsh` as data, not executable code, plus Obsidian's application registry and immediate vault directories under `~/ObsidianVaults`. Reconcile canonical paths with stable deterministic IDs; keep unavailable registered paths visible. Do not recursively search research roots. Store titles, favorites, one subject area per vault, descriptions and chosen cover paths under `~/Library/Application Support/VaultManager/metadata.json`. Use file locks, atomic rename, revision checks and backups on mutations. Reject malformed existing state rather than replacing it. Unknown group names remain supported. Use the reviewed curriculum Subject Map for initial editable defaults, with one section per vault; Courses contains numbered classes and Thermodynamics belongs only to Physics; unlisted utility vaults stay in Other.

## Stage 2 — Read-only status

Return metadata immediately, then inspect vaults in a bounded worker pool. Cache inspection separately with timestamps; show stale/unknown honestly. Inspect Git without optional locks, external diff or filesystem monitor hooks. Distinguish staged, unstaged, untracked and conflicts; show ahead/behind separately using cached upstream refs, never implying a live remote fetch. A nested vault uses its own path scope for content status/last commit and labels parent repository branch/upstream information. Count content, practice history, configuration and workspace changes separately. Last content edit is a bounded metadata scan excluding caches, `.git`, ordinary Obsidian config and symlink directories; label truncated or permission-limited results. Reading plugin manifests requires no execution or credential access.

## Stage 3 — Gallery and homepage

Native sidebar with All vaults, Favorites, subject areas and unavailable filter. Gallery uses coherent illustrated cards, a favorite action, status labels with accessible colors, title, description and shortcut. Search in memory across title, path, groups and aliases. Clicking a card opens its homepage inside the manager; a separate Open in Obsidian action launches the vault. Homepage contains path, latest commit, last meaningful edit, uncommitted categories, upstream state, plugin inventory and organization controls. Context menu includes Finder and copy path. Empty, loading, unavailable and error states remain actionable. Folder picker adds an existing vault only. Cover chooser supports existing local image files; default cards need no per-vault artwork.

## Stage 4 — Safe shortcut editing

Edit `oo` aliases in the actual shared shell registry with an atomic backup, collision checks, reserved-word checks and compare-and-swap revision. Ensure existing shell sessions reload before opening/completing/creating/removing aliases, and refuse stale registry writes rather than clobbering edits. Preserve all unrelated aliases and helper commands. Keep the native app and shell coordinated through one parser/transaction implementation. Test whitespace/Unicode paths, quote handling, duplicates and concurrent updates. Never rename the vault directory when changing its shortcut.

## Stage 5 — Distribution and verification

Generate a polished code-native icon, app bundle and command launcher. Build using the installed macOS SDK, ad-hoc sign locally, register with LaunchServices, and test launch from terminal. Include a small Alfred keyword workflow (`vaults`) so launching does not depend on Spotlight having indexed the new bundle yet. Do not overwrite an existing Alfred workflow. Inspect the actual native app with computer-use tooling: gallery, filtered search, detail, organization editing and persisted state. Do not open Fluid Dynamics on M4 while M1 is its writer.

## Tests and acceptance

Use isolated fixtures for malformed registries, duplicate aliases/paths, missing folders, metadata revisions, Git clean/dirty/conflict/ahead/behind and nested repositories. Verify no fixture inspection modifies tracked state. Test shell registry stale writes and atomic round trips before changing the user's helper. Measure real registry discovery and scan duration; search must never invoke filesystem traversal. Verify favorites, groups and titles persist across reload, installed plugin versions display, missing roots remain visible and errors are not reported as clean. Exercise native UI through screenshots and accessibility. Record exact completion, known limits, launcher paths and rollback instructions in README and VERIFICATION. No claim of cross-Mac ownership safety from Git colors alone.

## Rollout ordering

The Fluid Dynamics Git handoff and M1 dependency setup proceed separately. This app may read the local closed vault, but must not reopen or edit it during that ownership session. First build/test with disposable fixtures, then import the real registry read-only, then enable explicitly requested organization and shortcut editing. Keep pre-change helper/registry backups and source locally reviewable.
