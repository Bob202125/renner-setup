"""One host-local alias registry for every nav and Code Links client.

Renames retain redirects; retirement hides a name without breaking old links.
No cross-vault source rewriting is required. All writes use the same lock and
compare-and-swap preview, including migration of legacy project definitions.
"""
import copy
import csv
import io
import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path


def registry_path():
    return Path(os.environ.get('NAV_REGISTRY', str(Path(__file__).with_name('aliases.psv'))))


def valid(name):
    if name in {'create', 'list', 'search', 'open', 'copy', 'alphabetize', 'help', 'api'}:
        raise ValueError('This name is reserved by nav: '+name)
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', name):
        raise ValueError('Use a letter followed by letters, digits, hyphens or underscores')


def read(path):
    return path.read_text() if path.exists() else None


def canonical(path):
    if not isinstance(path, str) or not Path(path).expanduser().is_absolute():
        raise ValueError('Shared folder paths must be absolute')
    return str(Path(path).expanduser().resolve())


def load():
    raw = read(registry_path())
    data = {'version': 1, 'roots': {}, 'redirects': {}, 'retired': [], 'tags': {}}
    seen = set()
    for row in csv.reader(io.StringIO(raw or ''), delimiter='|'):
        if not row or not any(row):
            continue
        if not 2 <= len(row) <= 5:
            raise ValueError('Invalid nav alias row')
        name, path, tags, redirect, retired = row + [''] * (5-len(row))
        valid(name)
        if name in seen:
            raise ValueError('Duplicate nav alias: '+name)
        seen.add(name)
        data['tags'][name] = sorted(set(t.strip() for t in tags.split(',') if t.strip()))
        if redirect:
            valid(redirect)
            data['redirects'][name] = redirect
        else:
            data['roots'][name] = canonical(path)
        if retired:
            if retired != 'retired' or redirect:
                raise ValueError('Invalid retired alias: '+name)
            data['retired'].append(name)
    for name, target in data['redirects'].items():
        if target not in data['roots']:
            raise ValueError('Invalid nav alias redirect: '+name)
    return data, raw


def resolved(data, active=False):
    result = {name: canonical(path) for name, path in data['roots'].items()
              if not active or name not in data['retired']}
    if not active:
        result.update({name: canonical(data['roots'][target]) for name, target in data['redirects'].items()})
    return result


def roots(project, active=False):
    data, _ = load()
    result = resolved(data)
    cp = project/'.code-links.json'
    local = json.loads(cp.read_text()).get('roots', {}) if cp.exists() else {}
    for name, path in local.items():
        if name not in result or canonical(path) != result[name]:
            raise ValueError('Legacy vault-local alias '+name+' needs migration to the shared registry; open Manage linked folders. Local overrides are not allowed.')
    return {name: Path(path) for name, path in resolved(data, active).items()}


def encode(data):
    return json.dumps(data, ensure_ascii=False, indent=2)+'\n'


def encode_registry(data):
    out = io.StringIO(newline='')
    writer = csv.writer(out, delimiter='|', lineterminator='\n')
    for name, path in sorted(resolved(data).items()):
        writer.writerow([name, path, ','.join(data['tags'].get(name, [])),
                         data['redirects'].get(name, ''), 'retired' if name in data['retired'] else ''])
    return out.getvalue()


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.aliases-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def manager(project, action='list', name='', path='', new='', apply=False, token='', projects=None, legacy_registry=None, tags=None):
    hp = registry_path()
    hp.parent.mkdir(parents=True, exist_ok=True)
    # Lock before reading, constructing a preview, or checking its revision.
    with hp.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data, before = load()
        if action == 'list':
            items = [{'name': k, 'path': p, 'exists': Path(p).is_dir(), 'inherited': False,
                      'tags': data['tags'].get(k, []), 'shared': True, 'retired': k in data['retired'], 'redirect': data['redirects'].get(k)}
                     for k, p in resolved(data).items()]
            cp = project/'.code-links.json'
            local = json.loads(cp.read_text()).get('roots', {}) if cp.exists() else {}
            return {'items': items, 'registry': str(hp), 'legacy': local}
        proposed = copy.deepcopy(data)
        changes = []
        messages = []
        if action == 'migrate':
            if legacy_registry:
                old_path = Path(legacy_registry).expanduser().resolve()
                if old_path == hp.resolve():
                    raise ValueError('Cannot migrate the nav registry into itself')
                old = read(old_path)
                if old is not None:
                    legacy = json.loads(old)
                    for alias, target in legacy.items():
                        valid(alias)
                        target = canonical(target)
                        effective = resolved(proposed)
                        if alias in effective and effective[alias] != target:
                            raise ValueError('Alias conflict for '+alias+': nav '+effective[alias]+'; legacy '+target+'. No changes made.')
                        if alias not in effective:
                            proposed['roots'][alias] = target
                        messages.append(alias+': '+target)
                    if legacy:
                        changes.append((old_path, old, '{}\n'))
            for folder in sorted(set(str(Path(p).expanduser().resolve()) for p in (projects or [str(project)]))):
                cp = Path(folder)/'.code-links.json'
                old = read(cp)
                if old is None:
                    continue
                cfg = json.loads(old)
                local = cfg.get('roots', {})
                for alias, target in local.items():
                    valid(alias)
                    target = canonical(target)
                    effective = resolved(proposed)
                    if alias in effective and effective[alias] != target:
                        raise ValueError('Alias conflict for '+alias+': shared '+effective[alias]+'; '+str(cp)+' uses '+target+'. No changes made.')
                    if alias not in effective:
                        proposed['roots'][alias] = target
                    messages.append(alias+': '+target)
                if local:
                    cfg.pop('roots')
                    changes.append((cp, old, encode(cfg)))
        elif action == 'alphabetize':
            messages.append('Sort the shared nav registry without changing alias destinations.')
        else:
            valid(name)
            effective = resolved(data)
            if action == 'add':
                if name in effective:
                    raise ValueError('This shared alias already exists (including retired names): '+name)
                dest = canonical(path)
                if not Path(dest).is_dir():
                    raise ValueError('Choose an existing folder')
                matches = [k for k, p in effective.items() if p == dest]
                if matches:
                    raise ValueError('This folder already has a shared alias: '+', '.join(matches)+'. Use or rename that alias.')
                proposed['roots'][name] = dest
                messages.append('Add this alias for every vault and terminal client on this Mac.')
            else:
                if name not in data['roots']:
                    raise ValueError('Manage the canonical alias instead of a compatibility name')
                if action == 'move':
                    dest = canonical(path)
                    if not Path(dest).is_dir():
                        raise ValueError('Choose an existing folder')
                    if any(k != name and canonical(p) == dest for k, p in data['roots'].items()):
                        raise ValueError('This folder already belongs to another shared alias')
                    proposed['roots'][name] = dest
                    messages.append('Change '+name+': in EVERY vault on this Mac, from '+canonical(data['roots'][name])+' to '+dest+'. Compatibility names follow this change.')
                elif action == 'rename':
                    valid(new)
                    if new in effective:
                        raise ValueError('That shared alias is already reserved: '+new)
                    proposed['roots'][new] = proposed['roots'].pop(name)
                    for alias, target in list(proposed['redirects'].items()):
                        if target == name:
                            proposed['redirects'][alias] = new
                    proposed['redirects'][name] = new
                    proposed['tags'][new] = proposed['tags'].get(name, [])
                    proposed['retired'] = [new if x == name else x for x in proposed['retired']]
                    messages.append('Use '+new+': for new links. Existing '+name+': links and tracked excerpts keep working everywhere; no source files are rewritten.')
                elif action in ('remove', 'retire'):
                    if name not in proposed['retired']:
                        proposed['retired'].append(name)
                    messages.append('Hide this alias from new-link suggestions. Existing links keep working; the name remains reserved. Restore it here at any time.')
                elif action == 'tags':
                    proposed['tags'][name] = sorted(set(tags or []))
                    if any(not isinstance(t, str) or any(c in t for c in ',\n\r|') for t in proposed['tags'][name]):
                        raise ValueError('Tags cannot contain commas, pipes or newlines')
                    messages.append('Update shared folder tags.')
                elif action == 'restore':
                    proposed['retired'] = [x for x in proposed['retired'] if x != name]
                    messages.append('Show this alias in new-link suggestions again.')
                else:
                    raise ValueError('Unknown shared alias action')
        fingerprint = hashlib.sha256(encode([action, name, path, new, before, [(str(p), b, a) for p, b, a in changes], proposed]).encode()).hexdigest()
        report = {'action': action, 'name': name, 'new': new, 'path': path, 'references': [], 'anchors': 0,
                  'messages': messages, 'registry': str(hp), 'token': fingerprint, 'applied': False}
        if not apply:
            return report
        if token != fingerprint:
            raise ValueError('Shared aliases or legacy settings changed since preview; preview again')
        changes = [(hp, before, encode_registry(proposed))]+changes
        recovery = hp.parent/'.backups'/('aliases-'+str(time.time_ns()))
        recovery.mkdir(parents=True)
        write_text(recovery/'receipt.json', encode({**report, 'files': [str(p) for p, _, _ in changes]}))
        for i, (p, old, _) in enumerate(changes):
            if read(p) != old:
                raise ValueError('Concurrent modification; preview again')
            if old is not None:
                write_text(recovery/str(i), old)
        done = []
        try:
            for p, old, after in changes:
                if read(p) != old:
                    raise ValueError('Concurrent modification; preview again')
                write_text(p, after)
                done.append((p, old, after))
        except Exception:
            for p, old, after in reversed(done):
                if read(p) == after:
                    if old is None:
                        p.unlink()
                    else:
                        write_text(p, old)
            raise
        report.update(applied=True, recovery=str(recovery))
        return report
