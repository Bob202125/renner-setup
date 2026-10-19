# Renner's Obsidian and utilities handoff

Prepared from Grady's current local utilities on October 18, 2026. This archive is a recipient copy; Grady's setup was not changed. It contains code and a new-vault template, not his research vaults or annotations. No GitHub account is required to install this ZIP.

## Instructions for Renner's Codex

Please help Renner install this package on his own Mac. Read this document and review install.py before running it. Determine his macOS version, architecture, Python 3 availability, and whether Obsidian is installed. Do not copy any Grady-specific paths or accounts into Renner's configuration.

Run `python3 install.py` from this extracted directory. It verifies package checksums, requires Obsidian in /Applications and rsync, refuses to overwrite ~/utils, and backs up .zshrc before adding one source line. If ~/utils already exists, inspect it and merge deliberately with backups. Never replace Renner's existing vault registry or settings wholesale.

The Obsidian helpers use a bundled copy of the Vault Manager registry backend and discover Python from PATH. The graphical Vault Manager is not required. The recipient registry starts empty. Source ~/utils/renner-shell.zsh in a fresh zsh session, then run `ocreate renner_notes` (or Renner's preferred unused name). Verify the new folder, registry entry, copied plugins and theme, and actual opening in Obsidian. Test `oo renner_notes`. Confirm community-plugin loading with Renner and verify a sample Markdown note and equation render. Do not claim installation complete merely because files copied. If Obsidian opens without the intended vault, use its Open folder as vault flow to select the new folder.

## Included utilities

The active package includes oo/ocreate/orm; figure/hint formatting, figure numbering and code-free note copies; nav source with no saved aliases; pss source with no password database; Jupyter/Conda helper; Mathpix conversion source; Obsidian themes, snippets, and plugin binaries/settings. The pss tool stores its data in a plaintext file; it is included as requested, but do not populate it with credentials during setup. Conda/Jupyter and Mathpix are optional; install their dependencies only when Renner wants those features. Mathpix requires Renner's own account and credentials and may incur API charges. No credentials are supplied. Do not copy Grady's full .zshrc.

The template's local REST API credentials/private key were removed and that plugin is disabled. Personal shell-command configuration was removed and its plugin disabled. Execute Code's machine-specific interpreter configuration was omitted. These tools need fresh recipient configuration if requested. Other plugins may also require optional external applications (for example Pandoc, TeX, or Zotero); configure them for Renner rather than assuming they exist. This ZIP packages the current template; it does not guarantee every optional plugin works on his Obsidian version.

The `optional-machine-specific` directory holds fm/transfer, research backup, and cluster mirror source. These retain Grady-specific cluster/account/path defaults for reference. They are deliberately not installed or added as aliases. Before any use, configure Renner's own destinations and accounts, review deletion/transfer behavior, and dry-run; do not connect to Grady's clusters or backups. Relevant original docs are in utils/docs and utils/.fm.

The optional REA source archive and provenance file are included separately. It is not needed for Obsidian. Its dependencies/submodules are not bundled; follow its own documentation only if Renner asks to use REA.

The original read_me_obsidian_helpers.md is included for command reference but contains older installation details. This START-HERE document takes precedence for this handoff. No whole-home preferences, Git history, credential files, personal aliases, backups, or research notes are supplied.

## Handoff status

Package preparation and isolated creation/registration checks are performed on Grady's Mac. Installation and native Obsidian acceptance on Renner's Mac remain to be performed. Send the ZIP privately (for example AirDrop) and ask his Codex to read this START-HERE.md.

## Updated annotation and terminal support

Study Studio main.js, styles.css and manifest.json match the deployed research-vault build at packaging time. Annotation palettes and visibility settings are included with empty question/comment arrays. The copied visibility settings hide green sticky notes and red underlines, matching Grady; Renner may choose Show all. No actual paper annotations or practice records are included. See iterm/SETUP.md for the iTerm/Oh My Zsh/Powerlevel10k setup.
