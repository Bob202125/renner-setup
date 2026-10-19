# iTerm and zsh setup for Renner

Import Renner-profile.json as an additional iTerm profile; preserve existing profiles and do not replace the whole preferences plist. This is Grady's saved profile with a new ID/name, home-directory startup, and no automatic command or connection. Its font is MesloLGS NF Regular, size 13 (Monaco 12 fallback for non-ASCII). Install the font from Powerlevel10k's official font instructions if missing.

Grady uses Oh My Zsh with Powerlevel10k, and plugins git, zsh-autosuggestions, zsh-syntax-highlighting (last). Install these from their official upstreams only if Renner wants the same prompt. Back up existing .zshrc and .p10k.zsh. Merge theme/plugin/source lines without replacing his full shell config. Copy p10k.zsh to ~/.p10k.zsh after reviewing it, and source it after Oh My Zsh. Keep the utilities source line added by install.py.

The optional global-keyboard-map.json contains Grady's iTerm global key bindings. Bindings referring to his old profile now refer to the new profile ID. Merge only with Renner's agreement because these affect all profiles; back up current bindings first. No global preference import is automatic.

Verify a new iTerm session: correct font/glyphs, prompt, typing, and oo help. These are exported saved settings, not a claim that iTerm was tested on Renner's Mac. Do not import shell history, SSH config, credentials, or live sessions from Grady.
