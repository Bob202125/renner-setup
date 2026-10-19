# pss – A Tiny Clipboard-First Password Snippet Store

> **Keep low-stakes logins at your fingertips—right from the shell.**
>
> *pronounced “psss … your secrets are safe(ish) with me)”*

---

## 1  What Is `pss`?

`pss` is a single-file Python script that acts like a micro password manager for credentials you use often but **aren’t highly sensitive** (campus clusters, throw-away SaaS demo accounts, etc.).

* Stores data in **`~/utils/.pss/passwords.psv`** (pipe-separated values).
* Lets you **copy usernames/passwords straight to the system clipboard** (`pbcopy`, `xclip`, or `wl-copy`).
* Supports **tags** so you can group and recall related accounts.
* Maintains a full **undo-able** text file you can inspect or edit in any editor.
* No third-party dependencies—just stock Python 3.

> ⚠️ **NOT** for bank logins or anything you can’t afford to leak. Use Bitwarden, 1Password, `gopass`, etc. for those.

---

## 2  Installation

```bash
# 1  Put the script where it lives
mkdir -p ~/utils/.pss
cp pss.py ~/utils/.pss/
chmod +x ~/utils/.pss/pss.py

# 2  Expose it as a command (add to ~/.zshrc)
alias pss='python3 ~/utils/.pss/pss.py'
source ~/.zshrc
```

The **first run** creates `passwords.psv` if it doesn’t exist.

---

## 3  File Format (`passwords.psv`)

Each line:

```
entity|username|password|tag1,tag2,tag3
```

* `entity` - a short name (case-sensitive, no pipes).
* `tags`   - comma-separated, optional.

Example:

```
uiuc|gclopton|Tr1cky!Pa55|school,research
aws-demo|demo@example.com|hunter2|cloud
```

---

## 4  Command Cheat-Sheet

| Purpose                                                   | Command                                           |
| --------------------------------------------------------- | ------------------------------------------------- |
| **Copy username** to clipboard                            | `pss <entity> un`                                 |
| **Copy password** to clipboard                            | `pss <entity> pw`                                 |
| **Show** user + pass + tags on screen                     | `pss <entity> show`                               |
| **Create** a new entry                                    | `pss <entity> create un <username> pw <password>` |
| **Interactive change** (press **Enter** to keep existing) | `pss <entity> change`                             |
| **Delete** an entry (asks *are you sure?*)                | `pss <entity> del`                                |
| **Add tags**                                              | `pss <entity> tag add <tag …>`                    |
| **Remove tags**                                           | `pss <entity> tag rm  <tag …>`                    |
| **List all entries** with a given tag                     | `pss list <tag>`                                  |
| **Alphabetize** the whole file (tidy)                     | `pss alphabetize`                                 |
| **Help** / usage screen                                   | `pss --help` *or* `pss -h` *or* `pss help`        |

---

## 5  Examples

```bash
# Add a campus-cluster login
echo "\nAdding UIUC creds"
pss uiuc create un gclopton pw 'Tr1cky!Pa55'
pss uiuc tag add school research

# One-liner to grab password when logging in
ssh $(pss uiuc un)@hpc.example.edu # paste password with Ctrl-V / ⌘-V

# Forgot which accounts are tagged "research"?
pss list research

# Oops—typo in password
pss uiuc change   # prompts for new user/pass; hit Enter to keep same user

# Marie-Kondo that PSV
pss alphabetize
```

---

## 6  Security Notes

* The file is **plain text**; restrict permissions (`chmod 600`).
* Clipboard contents live until overwritten—clear it after use if paranoid.
* History expansion (`!`) in shells can expose passwords; quoting `'…'` or disabling history substitution (`setopt NO_HIST_SUBSTITUTION` in *zsh*) avoids surprises.
* For anything mission-critical or high-value, use a dedicated password manager.

---

## 7  Troubleshooting

| Symptom                            | Likely Cause / Fix                                                                          |
| ---------------------------------- | ------------------------------------------------------------------------------------------- |
| `KeyError: 'foo'`                  | No entry named *foo* yet. Check spelling or create it.                                      |
| `zsh: event not found: !Pa55`      | Shell history expansion on `!`. Wrap the password in single-quotes or escape `!` with `\!`. |
| Clipboard copy prints text instead | Neither `pbcopy`, `xclip`, nor `wl-copy` found—install one, or copy manually.               |

---

## 8  Roadmap / Ideas

* **Encryption** via GPG or age for medium-sensitive use-cases.
* **Fuzzy search** (`pss search <pattern>`) across entities & tags.
* **Password generation** (`pss gen 25` → returns a random 25-char string and stores it).

Pull requests welcome—keep it simple, keep it POSIX-friendly. ✌️

---

## 9  License

[MIT](LICENSE) – have fun and don’t blame me if you paste your root password on Twitter. 🙈

