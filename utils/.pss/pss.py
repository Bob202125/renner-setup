#!/usr/bin/env python3
# ~/utils/.pss/pss.py
import csv, os, sys, shutil, subprocess, getpass, textwrap

DATA = os.path.expanduser("~/utils/.pss/passwords.psv")
SEP  = "|"

# ────────────────────────── helpers ────────────────────────── #
def load():
    """Return {entity: [username, password, {tags…}]}"""
    if not os.path.exists(DATA):
        return {}
    book = {}
    with open(DATA, newline="") as f:
        for row in csv.reader(f, delimiter=SEP):
            entity, un, pw, *tags = row + [""] * (4 - len(row))
            book[entity] = [un, pw, set(t.strip() for t in tags[0].split(",") if t)]
    return book


def save(book):
    with open(DATA, "w", newline="") as f:
        w = csv.writer(f, delimiter=SEP)
        for ent in sorted(book):
            un, pw, tags = book[ent]
            w.writerow([ent, un, pw, ",".join(sorted(tags))])


def copy_to_clipboard(text):
    for cmd in ("pbcopy", "xclip", "wl-copy"):               # macOS, X11, Wayland
        if shutil.which(cmd):
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            p.communicate(text.encode())
            return
    print(text)                                              # fallback


def prompt(field, current):
    new = getpass.getpass(f"{field} [{current}]: ").strip()
    return current if new == "" else new


def usage():
    print(textwrap.dedent(f"""
        Usage:
          pss <entity> un|pw|show
          pss <entity> create un <username> pw <password>
          pss <entity> change
          pss <entity> del
          pss <entity> tag add <tag…>
          pss <entity> tag rm  <tag…>
          pss list <tag>
          pss alphabetize
    """).strip())


# ────────────────────────── main dispatch ──────────────────── #
def main():
    args = sys.argv[1:]
    if not args:
        usage(); return

    if args[0] in ("-h", "--help", "help"):         # ◀ NEW
        usage(); return                             # ◀ NEW

    # standalone commands first --------------------------------
    if args[0] == "alphabetize":
        save(load()); print("Alphabetized ✔")
        return

    if args[0] == "list" and len(args) == 2:
        tag = args[1]
        book = load()
        for ent, (un, _, tags) in book.items():
            if tag in tags:
                print(f"{ent}\t{un}")
        return

    # entity-scoped commands -----------------------------------
    if len(args) < 2:
        usage(); return

    ent, action, *rest = args
    book = load()

    # --- basic retrieval --------------------------------------
    if action == "un":
        copy_to_clipboard(book[ent][0])
        return
    if action == "pw":
        copy_to_clipboard(book[ent][1])
        return
    if action == "show":
        un, pw, tags = book[ent]
        print(f"username: {un}\npassword: {pw}\ntags: {', '.join(sorted(tags)) or '(none)'}")
        return

    # --- delete ----------------------------------------------
    if action == "del":
        if input(f"Delete {ent}? (y/N) ").lower() == "y":
            book.pop(ent, None); save(book)
        return

    # --- create ----------------------------------------------
    if action == "create":
        try:
            un_idx = rest.index("un")
            pw_idx = rest.index("pw")
            un = rest[un_idx + 1]
            pw = rest[pw_idx + 1]
        except (ValueError, IndexError):
            print("Syntax: pss <entity> create un <username> pw <password>"); return
        book[ent] = [un, pw, set()]
        save(book); return

    # --- change ----------------------------------------------
    if action == "change":
        if ent not in book:
            print("No such entry."); return
        un, pw, tags = book[ent]
        un = prompt("username", un)
        pw = prompt("password", pw)
        book[ent] = [un, pw, tags]
        save(book); return

    # --- tag operations --------------------------------------
    if action == "tag" and len(rest) >= 2:
        subcmd, *tags = rest
        if ent not in book:
            print("No such entry."); return
        tagset = book[ent][2]
        if subcmd == "add":
            tagset.update(tags)
        elif subcmd == "rm":
            tagset.difference_update(tags)
        else:
            print("Unknown tag subcommand (add|rm)."); return
        save(book); return

    print("Unknown action.")
    usage()


if __name__ == "__main__":
    main()

