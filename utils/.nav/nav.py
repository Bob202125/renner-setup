#!/usr/bin/env python3
"""Shared directory aliases: terminal navigation and Code Links use registry.py."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
import registry


def usage():
    print('''nav create <path> <alias>
nav <alias>                 # print path; shell wrapper changes directory
nav <alias> show|change|del|restore
nav <alias> tag add|rm <tags...>
nav list <tag> | search <text>
nav open <alias> | copy <alias>
nav alphabetize
nav api                    # structured JSON request on stdin, for integrations

Aliases are shared with every Code Links vault on this Mac.
Renaming preserves old links. del retires a name; restore makes it visible again.''')


def apply(action, **args):
    plan = registry.manager(Path.cwd(), action=action, **args)
    return registry.manager(Path.cwd(), action=action, **args, apply=True, token=plan['token'])


def confirm(plan):
    for message in plan['messages']:
        print(message)
    return input('Apply this shared change? (y/N) ').strip().lower() == 'y'


def main():
    args = sys.argv[1:]
    if args == ['api']:
        try:
            req = json.load(sys.stdin)
            project = Path(req.pop('root', str(Path.cwd()))).expanduser().resolve()
            print(json.dumps({'ok': True, 'result': registry.manager(project, **req)}))
        except Exception as e:
            print(json.dumps({'ok': False, 'error': str(e)})); return 1
        return 0
    if not args or args[0] in ('-h', '--help', 'help'):
        usage(); return 0
    data, _ = registry.load()
    book = registry.resolved(data)
    active = registry.resolved(data, active=True)
    if args[0] == 'alphabetize':
        apply('alphabetize'); print('Alphabetized shared aliases.'); return 0
    if args[0] in ('list', 'search') and len(args) == 2:
        for alias, path in sorted(active.items()):
            if (args[0] == 'list' and args[1] in data['tags'].get(alias, [])) or (args[0] == 'search' and args[1].lower() in (alias+' '+path).lower()):
                print(alias+'\t'+path)
        return 0
    if args[0] == 'create' and len(args) == 3:
        path = Path(args[1]).expanduser().resolve()
        alias = args[2]
        registry.valid(alias)
        if alias in book:
            raise ValueError('Alias already exists; use nav '+alias+' change')
        if not path.exists():
            if input('Create directory '+str(path)+'? (y/N) ').strip().lower() != 'y':
                return 0
            path.mkdir(parents=True)
        apply('add', name=alias, path=str(path)); print('Saved shared alias.'); return 0
    if args[0] in ('open', 'copy') and len(args) == 2:
        if args[1] not in book:
            raise ValueError('Unknown alias: '+args[1])
        path = book[args[1]]
        if args[0] == 'open':
            command = shutil.which('open') or shutil.which('xdg-open')
            if not command: raise ValueError('No file-manager command available')
            subprocess.run([command, path], check=True)
        else:
            command = shutil.which('pbcopy') or shutil.which('wl-copy') or shutil.which('xclip')
            if command:
                subprocess.run([command], input=path.encode(), check=True)
                print('Copied to clipboard.')
            else: print(path)
        return 0
    alias, *rest = args
    if alias not in book:
        raise ValueError('Unknown alias: '+alias)
    target = data['redirects'].get(alias, alias)
    if not rest:
        print(book[alias]); return 0
    cmd, *tail = rest
    if cmd == 'show':
        print('path: '+book[alias]+'\ntags: '+(', '.join(data['tags'].get(target, [])) or '(none)'))
        if alias != target: print('Compatibility alias for '+target)
        if target in data['retired']: print('Retired: existing links still work.')
    elif cmd in ('del', 'restore'):
        action = 'retire' if cmd == 'del' else 'restore'
        plan = registry.manager(Path.cwd(), action=action, name=target)
        if confirm(plan):
            registry.manager(Path.cwd(), action=action, name=target, apply=True, token=plan['token'])
    elif cmd == 'change':
        new = input('alias ['+target+']: ').strip() or target
        path = str(Path(input('path ['+book[alias]+']: ').strip() or book[alias]).expanduser().resolve())
        if new != target and path != book[alias]:
            raise ValueError('Rename and relocate in separate operations so each shared change is explicit.')
        if registry.load()[0] != data: raise ValueError('Aliases changed while you were editing; retry the command')
        action = 'rename' if new != target else 'move'
        kwargs = dict(action=action, name=target, new=new, path=path)
        plan = registry.manager(Path.cwd(), **kwargs)
        if confirm(plan):
            registry.manager(Path.cwd(), **kwargs, apply=True, token=plan['token'])
    elif cmd == 'tag' and len(tail) >= 2:
        sub, *tags = tail
        if sub not in ('add', 'rm'): raise ValueError('Use tag add|rm')
        # Build and apply one versioned request; a concurrent edit fails safely.
        old = set(data['tags'].get(target, []))
        updated = old.union(tags) if sub == 'add' else old.difference(tags)
        plan = registry.manager(Path.cwd(), action='tags', name=target, tags=sorted(updated))
        if registry.load()[0] != data: raise ValueError('Aliases changed; retry the tag command')
        registry.manager(Path.cwd(), action='tags', name=target, tags=sorted(updated), apply=True, token=plan['token'])
    else:
        raise ValueError('Unknown nav command; use nav help')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as e:
        print(str(e), file=sys.stderr); sys.exit(1)
