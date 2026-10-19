# Load this file from ~/.zshrc.
source "$HOME/utils/.obsidian_helpers"
alias pss='python3 "$HOME/utils/.pss/pss.py"'
alias cwdcopy='pwd | pbcopy'
export PATH="$HOME/utils/.jup/bin:$PATH"
mathpixpdf() { bash "$HOME/utils/mathpix/mathpixpdf.sh" "$@"; }
nav() {
 local dest
 case "$1" in
 create|list|alphabetize|search|open|copy|api|help|-h|--help) python3 "$HOME/utils/.nav/nav.py" "$@"; return;;
 esac
 case "$2" in
 show|change|del|restore|tag) python3 "$HOME/utils/.nav/nav.py" "$@"; return;;
 esac
 dest=$(python3 "$HOME/utils/.nav/nav.py" "$@") || return
 [[ -d "$dest" ]] && cd "$dest"
}
