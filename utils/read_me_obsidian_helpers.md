# Obsidian Helper Scripts – Quick‑Start Guide

> **Files involved**
>
> | File                           | Purpose                                        |
> | ------------------------------ | ---------------------------------------------- |
> | `~/utils/.obsidian_helpers`    | Main helper functions (`oo`, `ocreate`, `orm`) |
> | `~/utils/.obsidian_vaults.zsh` | Persistent list of vault names → paths         |
> | `~/utils/ObsidianConfig/`      | Shared `.obsidian` config for new vaults       |
> | `~/utils/ObsidianConfig/vault-root/` | Shared vault-root files such as `preamble.sty` and `Converting PDFs to Markdown.md` |
>
> **Dependencies**: macOS, Z‑sh 5+, [Yakitrak `obsidian-cli`](https://github.com/Yakitrak/obsidian-cli), Obsidian.app

---

## 1  What the helpers do

| Command                      | What it does                                                                                                                                       |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `oo <vault>`                 | Opens an **existing** vault by its *friendly name* (tab‑completion supported).                                                                     |
| `oo format figures <file>`   | Safely wraps standalone image + `Figure N` caption blocks in Obsidian `figure` callouts and italicizes figure mentions in prose, with backup and validation. |
| `oo format hints <file>`     | Safely converts bracketed `[Hint: ...]` text into bold parenthesized hints while skipping math/code regions, with backup and validation.         |
| `oo number figures <file>`   | Renumbers `[!figure]` callout header titles in source order, writes the numbering into the Markdown, and validates that only figure header numbering changed. |
| `oo strip code <file>`       | Creates a sibling `No Code/` copy of the note, removes fenced code blocks from the copy, and rewrites relative Markdown links so local images keep working. |
| `ocreate <vault> [base_dir]` | Creates a **new** vault folder → copies your shared config → registers it → launches Obsidian. Refuses if the vault name or folder already exists. |
| `orm <vault>`                | **Removes** a vault *mapping* (not the folder). Refuses if the folder still exists, so you can’t orphan data by mistake.                           |

All vault names & paths live in a single array (`OBS_VAULTS`) that is saved to `~/.obsidian_vaults.zsh` every time you create or remove a vault.

---

## 2  One‑time setup (already done)

```sh
# 1. Clone or copy helper file
mkdir -p ~/utils
#   (paste or symlink .obsidian_helpers into ~/utils)

# 2. Ensure shared config exists
mkdir -p ~/utils/ObsidianConfig
#   → drop appearance.json, hotkeys.json, plugins/, themes/, etc.

# 3. Install obsidian‑cli & add alias (handled inside helpers)
brew tap yakitrak/yakitrak
brew install yakitrak/yakitrak/obsidian-cli

# 4. Source the helpers from ~/.zshrc (add near the end)
[[ -f "$HOME/utils/.obsidian_helpers" ]] && source "$HOME/utils/.obsidian_helpers"
```

Open a **new terminal** (or `source ~/.zshrc`) and you’re ready.

---

## 3  Everyday usage examples

```sh
# list known vaults
oo <TAB>

# open an existing vault
oo research

# wrap figure blocks in the current note
oo format figures "/path/to/note.md"

# format bracketed hints in the current note
oo format hints "/path/to/note.md"

# renumber figure callout headers in the current note
oo number figures "/path/to/note.md"

# create a code-free copy in a sibling No Code/ folder
oo strip code "/path/to/note.md"

# create a new vault in the default directory (~/ObsidianVaults)
ocreate project_x

# create a new vault somewhere else
ocreate scratch /Volumes/ExternalDisk/Obsidian

# remove a vault mapping (after deleting its folder!)
rm -r ~/ObsidianVaults/scratch         # delete folder first
orm scratch                            # now remove mapping
```

### What happens during `ocreate`

1. **Name check** – abort if the name is already registered.
2. **Folder check** – abort if the target folder already exists.
3. Creates `<base>/<vault>/.obsidian/`.
4. Deletes Obsidian’s default `core-plugins.json` & `appearance.json`.
5. Copies **everything** from `~/utils/ObsidianConfig/` into that `.obsidian` folder.
6. Copies any shared vault-root files from `~/utils/ObsidianConfig/vault-root/` into the vault root.
7. Adds the vault to `OBS_VAULTS` and saves the DB.
8. Launches Obsidian (via `open -a Obsidian`).

### Go to Line in new and existing vaults

The shared config includes and enables `obsidian-go-to-line` (Go to Line), so future vaults created with `ocreate` inherit it automatically. Existing vaults are not changed: check each vault's Community plugins and remind the user to install Go to Line if absent, or enable it if installed but disabled.

Go to Line requires editing mode. From Reading view, press Cmd+E, open Cmd+P, choose **Go to Line: Go to line**, enter the Markdown source line number, and press Return. Verify the destination, then optionally return to Reading view with Cmd+E. No dedicated shortcut is assigned by this addition. A source line is not a rendered page number, and the destination may appear near the bottom of the viewport.

### What happens during `oo format figures`

1. Scans only for **standalone** image lines immediately followed by a `Figure N ...` caption line.
2. Skips figures already inside callouts.
3. Italicizes figure mentions in prose such as `Figure 2`, `Figure 2(a)`, and `Figures 10 and 11`, while skipping figure callouts and math regions delimited by `$...$` and `$$...$$`.
4. Builds the edited note in memory first.
5. Validates that non-formatting text is unchanged after normalizing figure blocks and figure-mention italics.
6. Writes a timestamped backup into a sibling `backups/` folder.
7. Replaces the note only if validation passes.
8. Is safe to rerun: already formatted callouts and already italicized figure mentions are left alone.

### What happens during `oo format hints`

1. Scans only for bracketed spans that begin with `[Hint:`.
2. Skips math regions delimited by `$...$` and `$$...$$`, as well as fenced code and inline code.
3. Replaces the outer square brackets with bold parenthesized formatting, preserving the exact hint text inside.
4. Builds the edited note in memory first.
5. Validates that non-formatting text is unchanged after normalizing bracketed and bold-parenthesized hint forms.
6. Writes a timestamped backup into a sibling `backups/` folder.
7. Replaces the note only if validation passes.
8. Is safe to rerun: already formatted `**(Hint: ...)**` spans are left alone.

### What happens during `oo number figures`

1. Scans only for real `[!figure]` callout header lines in the note.
2. Skips fake callout syntax inside fenced code blocks.
3. Renumbers figures in source order and writes that numbering into the header title text.
4. Handles blank figure headers, unnumbered figure titles, existing `Figure N` titles, and subfigure titles written as `Figure N(a)`, `Figure Na`, or `Figure N.a`, normalizing them to `Figure N(a)`.
5. Builds the edited note in memory first.
6. Validates that only figure header numbering changed after normalizing figure headers.
7. Writes a timestamped backup into a sibling `backups/` folder.
8. Replaces the note only if validation passes.
9. Is safe to rerun: already-correct figure numbering is left alone.

### What happens during `oo strip code`

1. Creates a sibling `No Code/` folder next to the source note if it does not already exist.
2. Copies the note into that folder under the same file name.
3. Removes fenced code blocks delimited by triple backticks or tildes from the copy.
4. Leaves images, prose, callouts, and other non-code content intact.
5. Rewrites relative Markdown links in the copied file so links like `./images/...` still resolve correctly from the new `No Code/` location.
6. Leaves the original note unchanged.

---

## 4  Updating shared config

1. Edit `.obsidian` defaults inside `~/utils/ObsidianConfig/`.
2. Edit vault-root defaults such as `preamble.sty` and `Converting PDFs to Markdown.md` inside `~/utils/ObsidianConfig/vault-root/`.
3. New vaults automatically inherit both.
4. Existing vaults keep their own settings – copy over manually if desired.

---

## 5  Troubleshooting

| Symptom                                  | Likely cause & fix                                              |
| ---------------------------------------- | --------------------------------------------------------------- |
| `oo something` → "Unknown vault"         | Name not in `OBS_VAULTS`. Run `ocreate`, or edit the DB file.   |
| `oo format figures ...` fails validation | The note is too irregular for the safe matcher; inspect manually. |
| `oo number figures ...` fails validation | Something other than figure header numbering appears to have changed; inspect the note or restore from backup. |
| `ocreate x` refuses with "folder exists" | Pick another name **or** delete/rename the folder first.        |
| `orm x` complains folder exists          | Delete or move the folder, then rerun `orm`.                    |
| `open: command not found`                | `$PATH` missing `/usr/bin`; restore or run from macOS, not SSH. |

---

## 6  Advanced

* **Manually edit database** – open `~/.obsidian_vaults.zsh`, adjust the associative‑array assignment, save, then `source ~/.zshrc`.
* **Bulk clean‑up duplicates** –

  ```sh
  zsh -c 'source ~/utils/.obsidian_helpers; _save_vault_db'
  ```

  (Writes a deduplicated DB using whatever is loaded in memory.)
* **Change default vault folder** – set a different path in `ocreate`’s `base` default or pass a custom `base_dir` per call.

---

Happy vaulting! 🎉
