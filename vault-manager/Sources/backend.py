#!/usr/bin/env python3
"""Vault Manager: local registry and read-only inspection. No shell execution."""
import concurrent.futures, contextlib, datetime, fcntl, hashlib, json, os, re, shlex, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HOME = Path(os.environ.get('VM_HOME', str(Path.home())))
STATE = Path(os.environ.get('VM_STATE', str(HOME/'Library/Application Support/VaultManager')))
REGISTRY = HOME/'utils/.obsidian_vaults.zsh'
RESERVED = {'open','format','number','strip','date','help','-h','--help'}

def digest(b): return hashlib.sha256(b).hexdigest()
def read_json(p, default):
    if not p.exists(): return default
    return json.loads(p.read_text())
def atomic(p, value, raw=False):
    p.parent.mkdir(parents=True, exist_ok=True)
    data = value if raw else json.dumps(value, ensure_ascii=False, indent=2).encode()
    fd, temp = tempfile.mkstemp(dir=p.parent, prefix='.'+p.name)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(temp,p)
    finally:
        if os.path.exists(temp): os.unlink(temp)
@contextlib.contextmanager
def lock(p):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        yield

def registry():
    b = REGISTRY.read_bytes() if REGISTRY.exists() else b''
    return parse_registry(b.decode()), digest(b)
def parse_registry(s):
    if not s.strip(): return {}
    m = re.fullmatch(r'\s*typeset\s+(?:-[gA]+\s+)+OBS_VAULTS=\(\s*(.*?)\s*\)\s*',s,re.S)
    if not m: raise ValueError('Unrecognized oo registry format; left unchanged.')
    result={}
    for token in shlex.split(m[1]):
        entry=re.fullmatch(r'\[([^\]]+)\]=(.*)',token,re.S)
        if not entry: raise ValueError('Invalid oo registry entry; left unchanged.')
        k,v=entry.groups()
        if k in result: raise ValueError('Duplicate oo shortcut: '+k)
        if not v.startswith('/'): raise ValueError('oo paths must be absolute.')
        result[k]=v
    return result

def encode_registry(values):
    return ('typeset -g -A OBS_VAULTS=( '+ ' '.join('['+shlex.quote(k)+']='+shlex.quote(v) for k,v in sorted(values.items()))+' )\n').encode()
def replace_registry(values, expected):
    with lock(REGISTRY.with_suffix('.zsh.lock')):
        _, rev=registry()
        if rev != expected: raise ValueError('Shortcuts changed in another window. Reload and try again.')
        if REGISTRY.exists():
            backup=STATE/'backups'/('shortcuts-'+str(time.time_ns())+'.zsh')
            backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(REGISTRY,backup)
        atomic(REGISTRY,encode_registry(values),raw=True)
    return digest(encode_registry(values))
def canonical(p): return os.path.realpath(os.path.expanduser(str(p)))
def ident(p): return digest(canonical(p).encode())[:20]
def default_groups(name):
    mapping=read_json(Path(__file__).with_name('areas.json'),{'vaults':{}})['vaults']
    return mapping.get(name,['Other'])
def metadata():
    d=read_json(STATE/'metadata.json',{'revision':0,'vaults':{}})
    if not isinstance(d.get('vaults'),dict) or not isinstance(d.get('revision'),int): raise ValueError('Invalid saved organization data; preserved for recovery.')
    return d

def discover():
    aliases,rev=registry(); meta=metadata(); paths={canonical(p) for p in aliases.values()}
    obs=read_json(HOME/'Library/Application Support/obsidian/obsidian.json',{})
    paths.update(canonical(v['path']) for v in obs.get('vaults',{}).values() if isinstance(v,dict) and v.get('path'))
    base=HOME/'ObsidianVaults'
    if base.is_dir(): paths.update(canonical(p) for p in base.iterdir() if p.is_dir() and (p/'.obsidian').is_dir())
    paths.update(v['path'] for v in meta['vaults'].values() if v.get('path'))
    cache=read_json(STATE/'cache.json',{})
    out=[]
    for p in sorted(paths):
        i=ident(p); v=meta['vaults'].get(i,{})
        aa=sorted(k for k,value in aliases.items() if canonical(value)==p)
        name=Path(p).name.replace('_',' ').replace('-',' ').title()
        if Path(p).name=='docs': name=Path(p).parent.name.replace('-',' ').title()+' Docs'
        out.append(dict(id=i,path=p,title=v.get('title',name),groups=v.get('groups',default_groups(Path(p).parent.name.replace('-','_')+'_docs' if Path(p).name=='docs' else Path(p).name)),favorite=v.get('favorite',False),description=v.get('description',''),cover=v.get('cover',''),aliases=aa,available=(Path(p)/'.obsidian').is_dir(),status=cache.get(i)))
    return dict(vaults=out,revision=meta['revision'],registryRevision=rev)

def update(req):
    with lock(STATE/'metadata.lock'):
        m=metadata()
        if req['revision']!=m['revision']: raise ValueError('Organization changed in another window. Reload before saving.')
        p=canonical(req['path']); i=ident(p)
        if not (Path(p)/'.obsidian').is_dir() and i not in m['vaults'] and i not in [v['id'] for v in discover()['vaults']]: raise ValueError('Choose an existing Obsidian vault folder.')
        value=m['vaults'].get(i,{}).copy()
        for key in ['title','description','cover','favorite','groups']:
            if key in req: value[key]=req[key]
        if not str(value.get('title','')).strip(): raise ValueError('Give the vault a display name.')
        value['groups']=list(dict.fromkeys(str(g).strip() for g in value.get('groups',['Other']) if str(g).strip())) or ['Other']
        if len(value['groups']) != 1: raise ValueError('Choose one area for each vault.')
        value['path']=p; m['vaults'][i]=value; m['revision']+=1
        if (STATE/'metadata.json').exists(): shutil.copy2(STATE/'metadata.json',STATE/'metadata.previous.json')
        atomic(STATE/'metadata.json',m)
    return discover()

def shortcut(req):
    values,rev=registry()
    if rev != req['registryRevision']: raise ValueError('Shortcuts changed; refresh before saving.')
    alias=req['alias'].strip(); old=req.get('old','')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',alias) or alias in RESERVED: raise ValueError('Use letters, numbers, _ or -. This name must not be an oo command.')
    p=canonical(req['path'])
    if alias in values and canonical(values[alias])!=p: raise ValueError('That shortcut already belongs to another vault.')
    if old and old!=alias:
        if old not in values or canonical(values[old])!=p: raise ValueError('Original shortcut changed; refresh first.')
        del values[old]
    values[alias]=p; replace_registry(values,rev)
    return discover()

def git(path,args,timeout=12):
    env=dict(os.environ,GIT_OPTIONAL_LOCKS='0',LC_ALL='C',GIT_TERMINAL_PROMPT='0')
    p=subprocess.run(['/usr/bin/git','-c','core.fsmonitor=false','-c','core.untrackedCache=false','-C',path,*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,env=env)
    return p.returncode,p.stdout.decode('utf-8','replace'),p.stderr.decode('utf-8','replace')
def category(p):
    if p.startswith('.obsidian/'):
        if 'workspace' in p: return 'workspace'
        if ('study-studio' in p or 'slide-studio' in p or 'ink-studio' in p) and (p.endswith('data.json') or '/attempts/' in p): return 'learning'
        return 'configuration'
    return 'content'
def inspect(path):
    began=time.monotonic(); result=dict(checkedAt=time.time(),state='unknown',content=0,learning=0,configuration=0,workspace=0,staged=0,unstaged=0,untracked=0,conflicts=0,ahead=0,behind=0,plugins=[])
    root=Path(path)
    if not (root/'.obsidian').is_dir(): return {**result,'state':'missing','error':'Folder unavailable or no .obsidian directory.'}
    enabled=read_json(root/'.obsidian/community-plugins.json',[])
    plugins=root/'.obsidian/plugins'
    if plugins.is_dir():
        for p in plugins.glob('*/manifest.json'):
            try:
                d=read_json(p,{})
                result['plugins'].append({'name':d.get('name',p.parent.name),'version':str(d.get('version','?')),'enabled':d.get('id',p.parent.name) in enabled})
            except (ValueError,OSError): result['plugins'].append({'name':p.parent.name,'version':'Unreadable manifest','enabled':False})
    code,out,_=git(path,['rev-parse','--show-toplevel'])
    if code: result['state']='noGit'
    else:
        repo=out.strip(); result['repository']=repo; result['nested']=canonical(repo)!=canonical(path)
        code,out,err=git(path,['status','--porcelain=v1','-z','--untracked-files=normal','--','.'])
        if code: result.update(state='error',error=err.strip())
        else:
            entries=iter(out.split('\0'))
            for entry in entries:
                if not entry: continue
                xy,p=entry[:2],entry[3:]
                if 'R' in xy or 'C' in xy: next(entries,None)
                if result['nested']: p=os.path.relpath(os.path.join(repo,p),path)
                result[category(p)]+=1
                if xy=='??': result['untracked']+=1
                else:
                    result['staged']+=int(xy[0]!=' '); result['unstaged']+=int(xy[1]!=' ')
                    result['conflicts']+=int('U' in xy or xy in ('AA','DD'))
            result['state']='conflict' if result['conflicts'] else ('dirty' if sum(result[k] for k in ('content','learning','configuration','workspace')) else 'clean')
        _,out,_=git(path,['symbolic-ref','--short','-q','HEAD']); result['branch']=out.strip() or 'Detached HEAD'
        _,out,_=git(path,['log','-1','--format=%ct%x00%h%x00%s','--','.'])
        parts=out.strip().split('\0',2)
        if len(parts)==3: result.update(commitTime=float(parts[0]),commit=parts[1],commitSubject=parts[2])
        code,out,_=git(path,['rev-parse','--abbrev-ref','--symbolic-full-name','@{upstream}'])
        if not code:
            result['upstream']=out.strip()
            code,out,_=git(path,['rev-list','--left-right','--count','HEAD...@{upstream}'])
            if not code: result['ahead'],result['behind']=map(int,out.split())
    latest=0; count=0; truncated=False
    exclude={'.git','node_modules','.venv','venv','__pycache__','.DS_Store'}
    for base,dirs,files in os.walk(path,followlinks=False):
        dirs[:]=[d for d in dirs if d not in exclude and d!='.obsidian' and not Path(base,d).is_symlink()]
        for f in files:
            if f.startswith('.') or f.endswith(('.pyc','.tmp','.lock')): continue
            try:
                stat=Path(base,f).lstat()
                if not Path(base,f).is_symlink(): latest=max(latest,stat.st_mtime)
            except OSError: truncated=True
            count+=1
        if count>=40000 or time.monotonic()-began>6: truncated=True; break
    # Learning records are meaningful despite living in plugin data.
    for p in [root/'.obsidian/plugins/study-studio/data.json']:
        if p.exists(): latest=max(latest,p.stat().st_mtime)
    result.update(lastEdit=latest,editPartial=truncated,filesSampled=count,duration=round(time.monotonic()-began,3))
    return result

def scan():
    d=discover(); cache=read_json(STATE/'cache.json',{})
    def work(v):
        try: return v['id'],inspect(v['path'])
        except Exception as e: return v['id'],dict(state='error',error=str(e),checkedAt=time.time(),plugins=[])
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for i,status in pool.map(work,d['vaults']): cache[i]=status
    with lock(STATE/'cache.lock'): atomic(STATE/'cache.json',cache)
    return discover()

def main():
    action=sys.argv[1]; req=json.load(sys.stdin) if action in ('update','shortcut','inspect') else {}
    if action=='discover': return discover()
    if action=='scan': return scan()
    if action=='update': return update(req)
    if action=='shortcut': return shortcut(req)
    if action=='inspect': return inspect(req['path'])
    if action=='shell-save':
        values=parse_registry(sys.stdin.read()); replace_registry(values,sys.argv[2]); return {'ok':True}
    if action=='registry-revision': print(registry()[1]); return None
    raise ValueError('Unknown action')
if __name__=='__main__':
    try:
        result=main()
        if result is not None: print(json.dumps(result,ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'error':str(e)})); sys.exit(1)
