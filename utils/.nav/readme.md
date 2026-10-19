# nav – Warp‑speed directory jumping

> Save a path once, reach it forever: `nav sim` ➜ `cd ~/projects/semiconductor-sim`.
>
> Now with **search, open, and copy‑to‑clipboard** goodness.

---

## 1  What is *nav*?

* **Python 3 utility** (`nav.py` and `registry.py`) + tiny shell wrapper.
* Stores aliases in **`~/utils/.nav/aliases.psv`** (pipe‑separated).
* Jump (`cd`), **search**, **copy**, **open in GUI**, **tags**, duplicate checks, auto‑mkdir.
* Zero non‑stdlib dependencies—works on macOS, Linux, and headless clusters.
* The same registry is used by Code Links in Obsidian and Neovim; vaults cannot override named aliases.

> ⚠️  nav is a convenience tool, not a security layer. The paths are plain text.

---

## 2  Installation

```bash
# 1  Install script
mkdir -p ~/utils/.nav
cp nav.py registry.py ~/utils/.nav/
chmod +x ~/utils/.nav/nav.py

# 2  Add wrapper to ~/.zshrc  (adapt to ~/.bashrc on clusters)
function nav() {
  # top‑level commands that need no cd
  if [[ "$1" == create || "$1" == list || "$1" == alphabetize \
        || "$1" == search || "$1" == open || "$1" == copy \
        || "$1" == api || "$1" == help || "$1" == -h || "$1" == --help ]]; then
    python3 ~/utils/.nav/nav.py "$@"; return
  fi
  # alias‑scoped but stay‑put commands
  if [[ "$2" == show || "$2" == change || "$2" == del || "$2" == restore || "$2" == tag ]]; then
    python3 ~/utils/.nav/nav.py "$@"; return
  fi
  # plain alias → cd
  dest=$(python3 ~/utils/.nav/nav.py "$@")
  [[ -d $dest ]] && cd "$dest" || echo "No such directory: $dest"
}

source ~/.zshrc  # reload shell once
```

On HPC clusters that default to *bash*, translate the wrapper accordingly.

---

## 3  PSV file format

```
alias|/absolute/path|tag1,tag2|redirect-target|retired
```

The last two fields are optional. Existing three-field rows remain supported. Leave the redirect field empty for a canonical alias. A compatibility name refers to its canonical alias; retiring a canonical alias hides it from suggestions while keeping existing links valid. Use the utility or vault interface to edit the registry.

Example:

```
sim|~/projects/semiconductor-sim|school,research
notes|~/Dropbox/Notes|
```

---

## 4  Command cheat‑sheet

| Action                      | Command                              |
| --------------------------- | ------------------------------------ |
| **Jump (cd)**               | `nav <alias>`                        |
| **Create alias**            | `nav create <path> <alias>`          |
| **Show** path + tags        | `nav <alias> show`                   |
| **Change** alias/path       | `nav <alias> change`                 |
| **Retire** alias            | `nav <alias> del`                    |
| **Restore** alias           | `nav <alias> restore`                |
| **Add tags**                | `nav <alias> tag add <tag…>`         |
| **Remove tags**             | `nav <alias> tag rm <tag…>`          |
| **List by tag**             | `nav list <tag>`                     |
| **Search** substring        | `nav search <text>`                  |
| **Copy path to clipboard**  | `nav copy <alias>`                   |
| **Open in Finder/Nautilus** | `nav open <alias>`                   |
| **Alphabetize file**        | `nav alphabetize`                    |
| **Help**                    | `nav -h` / `nav --help` / `nav help` |

### Special behaviour on `create`

* Verifies directory exists; offers to `mkdir -p` if missing.
* Rejects conflicting names and duplicate directory registrations. Use the existing alias or rename it. Retired and compatibility names remain reserved.

---

## 5  Everyday snippets

```bash
# Save current directory as an alias
nav create "$(pwd)" here

# Quick jump
nav here

# Copy its path to clipboard
nav copy here       # "📋  copied to clipboard"

# GUI open (ignored on headless servers)
nav open here

# Tag & search
nav here tag add project  
nav search project
```

Optional helper to copy *current* directory instantly (add to shell rc):

```zsh
alias cwdcopy='pwd | pbcopy'          # macOS
# alias cwdcopy='pwd | xclip -sel clip'  # Linux/X11
```

---

## 6  How it works

1. Wrapper parses the command line to decide whether to `cd`.
2. `registry.py` owns reads, conflict checks, locked atomic writes, and recovery copies in `.backups/`. Both the terminal utility and Code Links call it. Changes made during an open edit are rejected instead of overwritten.
3. Clipboard uses `pbcopy`, `xclip`, or `wl-copy`; falls back to echo.

---

## 7  FAQ

| Issue                                             | Remedy                                                           |
| ------------------------------------------------- | ---------------------------------------------------------------- |
| `Unknown alias.`                                  | Check spelling or `nav search <txt>`.                            |
| Clipboard copy prints path instead of silent copy | Install `pbcopy` (macOS), `xclip` (X11), or `wl-copy` (Wayland). |
| `open` says no command                            | Cluster/headless session—feature skipped.                        |
| Need same aliases on another machine | Preserve the same names but map them to that machine's actual directories. Do not blindly overwrite the other Mac's registry. |

---

## 8  Roadmap ideas

* Fuzzy‑frecency ranking (`nav top`).
* Shell tab‑completion for aliases.
* Export/import helpers.
  PRs welcome!



## Shared aliases in Obsidian and Neovim

In Obsidian, run **Code Links: Manage linked folders**. Creating, relocating, renaming, retiring, or restoring an alias here changes the same `aliases.psv` used by `nav`. Reopen a gallery to refresh its source folders. Neovim refreshes completion within 30 seconds, or immediately with `:CodeLinksRefresh`. Resolving an existing link reads the current registry.

Renaming keeps the old spelling as a compatibility name. Relocating the canonical alias updates those names too. No notes or tracked excerpts are rewritten. `del` now retires rather than erases an alias, preventing a forgotten link in another vault from breaking or pointing to unrelated data later.

On 2026-10-07, eight previous host-level Code Links aliases and the lab's `qm` and `ceria` aliases were migrated without conflicts. The former Code Links JSON registry is empty, and the lab's local definitions were removed. A conflicting definition encountered in an older vault fails explicitly and can be imported through the manager only after resolving the conflict.

For structured integrations, `python3 ~/utils/.nav/nav.py api` accepts a JSON request on stdin. Mutations require a preview token followed by an apply request; both use the same lock and compare-and-swap checks. `NAV_REGISTRY` can point to an isolated PSV registry for tests.
