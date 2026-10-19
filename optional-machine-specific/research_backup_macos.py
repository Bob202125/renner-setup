#!/usr/bin/env python3
"""Backup-only macOS research capture; never deletes sources or remote objects."""
import os, sys, json, stat, hashlib, subprocess, time, fcntl, ctypes, base64
from pathlib import Path, PurePosixPath
import tarfile
HOME=Path.home(); BASE=Path(__file__).resolve().parent
RC='/opt/homebrew/bin/rclone'; CONFIG=HOME/'.config/rclone/rclone.conf'
LIB=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True)
LIB.listxattr.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int];LIB.listxattr.restype=ctypes.c_ssize_t
LIB.getxattr.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int];LIB.getxattr.restype=ctypes.c_ssize_t
LIB.acl_get_link_np.argtypes=[ctypes.c_char_p,ctypes.c_int];LIB.acl_get_link_np.restype=ctypes.c_void_p
LIB.acl_to_text.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ssize_t)];LIB.acl_to_text.restype=ctypes.c_void_p
LIB.acl_free.argtypes=[ctypes.c_void_p]
LIB.acl_from_text.argtypes=[ctypes.c_char_p];LIB.acl_from_text.restype=ctypes.c_void_p
LIB.acl_set_link_np.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.c_void_p];LIB.acl_set_link_np.restype=ctypes.c_int
LIB.setxattr.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int];LIB.setxattr.restype=ctypes.c_int
LIB.removexattr.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];LIB.removexattr.restype=ctypes.c_int
def attrs(p):
 b=os.fsencode(p); n=LIB.listxattr(b,None,0,1)
 if n<0: raise OSError(ctypes.get_errno(),'listxattr failed',str(p))
 buf=ctypes.create_string_buffer(n)
 if n and LIB.listxattr(b,buf,n,1)<0:raise OSError('xattrs changed')
 result={}
 for a in sorted(x for x in buf.raw.split(b'\0') if x):
  size=LIB.getxattr(b,a,None,0,0,1)
  if size<0:raise OSError('getxattr failed')
  v=ctypes.create_string_buffer(size)
  if LIB.getxattr(b,a,v,size,0,1)!=size:raise OSError('xattr size changed')
  result[os.fsdecode(a)]=base64.b64encode(v.raw).decode()
 acl=LIB.acl_get_link_np(b,0x100)
 if not acl:
  if ctypes.get_errno()==2:return result,''
  raise OSError(ctypes.get_errno(),'ACL unavailable',str(p))
 size=ctypes.c_ssize_t();ptr=LIB.acl_to_text(acl,ctypes.byref(size))
 if not ptr:LIB.acl_free(acl);raise OSError('ACL text unavailable')
 acltext=ctypes.string_at(ptr,size.value).decode();LIB.acl_free(ptr);LIB.acl_free(acl)
 return result,acltext
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def scan(base,roots,hashes=False):
 out={}
 for rel in roots:
  root=base/rel
  if root.is_symlink() or not root.is_dir():raise RuntimeError('Invalid source root: '+str(root))
  paths=[root]
  for dp,ds,fs in os.walk(root,followlinks=False,onerror=lambda e:(_ for _ in ()).throw(e)):
   paths.extend(Path(dp)/n for n in sorted(ds+fs))
  for p in paths:
   s=p.lstat();kind='file' if stat.S_ISREG(s.st_mode) else 'dir' if stat.S_ISDIR(s.st_mode) else 'link' if stat.S_ISLNK(s.st_mode) else 'special'
   if kind=='special' or getattr(s,'st_flags',0)&0x40000000:raise RuntimeError('Special/placeholder source: '+str(p))
   x,a=attrs(p)
   d=dict(kind=kind,mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,gid=s.st_gid,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,birthtime=getattr(s,'st_birthtime',None),flags=s.st_flags,dev=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,xattrs=x,acl=a)
   if kind=='file':
    d['size']=s.st_size
    if hashes:
     d['sha256']=sha(p)
     z=p.stat()
     if (z.st_size,z.st_mtime_ns,z.st_ctime_ns)!=(s.st_size,s.st_mtime_ns,s.st_ctime_ns):raise RuntimeError('File changed while hashing')
   if kind=='link':d['target']=os.readlink(p)
   out[str(p.relative_to(base))]=d
 return out
def portable(d):
 r={k:v for k,v in d.items() if k not in ['ctime_ns','birthtime','dev','inode','nlink','sha256']}
 r['xattrs']={k:v for k,v in d['xattrs'].items() if k!='com.apple.provenance'}
 return r
def same(a,b,content=False):
 if a.keys()!=b.keys():raise RuntimeError('Tree membership mismatch')
 bad=[p for p in a if portable(a[p])!=portable(b[p]) or (content and a[p].get('sha256')!=b[p].get('sha256'))]
 if bad:raise RuntimeError('Content/metadata mismatch: '+repr(bad[:5]))
def save(p,d):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');tmp.replace(p)
def call(args,log):
 with open(log,'ab') as f:subprocess.run(args,stdout=f,stderr=f,check=True)
def rc(args,log):call([RC,'--config',str(CONFIG),'--retries','3','--low-level-retries','5','--contimeout','30s','--timeout','5m']+args,log)
def tar_chunks(snapshot,roots,chunks,log):
 chunks.mkdir(); parts=[]
 entries=[]
 for rel in roots:
  root=snapshot/rel;entries.append(rel)
  for dp,ds,fs in os.walk(root,followlinks=False):entries.extend(str((Path(dp)/n).relative_to(snapshot)) for n in sorted(ds+fs))
 listing=chunks.parent/'tar-paths.nul';listing.write_bytes(b''.join(os.fsencode(n)+b'\0' for n in entries))
 with open(log,'ab') as err:
  proc=subprocess.Popen(['/usr/bin/tar','--format=pax','--no-mac-metadata','--no-acls','--no-xattrs','--no-fflags','-cf','-','-C',str(snapshot),'--null','--no-recursion','-T',str(listing)],stdout=subprocess.PIPE,stderr=err)
  try:
   done=False
   while not done:
    path=chunks/('part-%05d'%len(parts));size=0;h=hashlib.sha256()
    with open(path,'wb') as f:
     while size<2*1024**3:
      b=proc.stdout.read(min(8*1024**2,2*1024**3-size))
      if not b:done=True;break
      f.write(b);h.update(b);size+=len(b)
    if size:parts.append(dict(name=path.name,size=size,sha256=h.hexdigest()))
    else:path.unlink()
   if proc.wait()!=0:raise RuntimeError('tar creation failed')
  finally:
   if proc.poll() is None:proc.terminate();proc.wait()
 return parts
def extract(chunks,parts,dest,log):
 # Treat literal ._ files as data; macOS bsdtar otherwise folds them into metadata.
 dest.mkdir();expected=json.loads((chunks.parent/'captured-manifest.json').read_text());seen=set()
 for d in parts:
  if sha(chunks/d['name'])!=d['sha256']:raise RuntimeError('Chunk hash mismatch')
 proc=subprocess.Popen(['/bin/cat']+[str(chunks/d['name']) for d in parts],stdout=subprocess.PIPE)
 try:
  with tarfile.open(fileobj=proc.stdout,mode='r|') as archive:
   for member in archive:
    name=member.name.rstrip('/');path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or name not in expected or name in seen:raise RuntimeError('Unexpected archive member')
    seen.add(name);d=expected[name]
    for parent in path.parents:
     if str(parent)!='.' and (dest/str(parent)).is_symlink():raise RuntimeError('Archive path traverses link')
    if member.issym():
     if d['kind']!='link' or member.linkname!=d['target']:raise RuntimeError('Link mismatch')
    elif member.islnk():
     if d['kind']!='file' or member.linkname not in expected or expected[member.linkname]['kind']!='file':raise RuntimeError('Hardlink mismatch')
    elif member.isfile():
     if d['kind']!='file' or member.size!=d['size']:raise RuntimeError('File mismatch')
    elif member.isdir():
     if d['kind']!='dir':raise RuntimeError('Directory mismatch')
    else:raise RuntimeError('Special archive member')
    archive.extract(member,dest,filter='fully_trusted')
  if proc.wait()!=0 or seen!=expected.keys():raise RuntimeError('Incomplete restore')
 finally:
  if proc.poll() is None:proc.terminate();proc.wait()
def restore_metadata(base,manifest):
 # Apply portable metadata from the verified manifest; directories last.
 for rel,d in sorted(manifest.items(),key=lambda x:(x[1]['kind']=='dir',-x[0].count('/'))):
  p=base/rel;b=os.fsencode(p);current,current_acl=attrs(p)
  for name in set(current)-set(d['xattrs'])-{'com.apple.provenance'}:
   if LIB.removexattr(b,os.fsencode(name),1)!=0:raise OSError('Cannot remove extra restored xattr')
  for name,value in d['xattrs'].items():
   if name!='com.apple.provenance' and current.get(name)!=value:
    raw=base64.b64decode(value);buf=ctypes.create_string_buffer(raw)
    if LIB.setxattr(b,os.fsencode(name),buf,len(raw),0,1)!=0:raise OSError('Cannot restore xattr '+name)
  st=p.lstat()
  if (st.st_uid,st.st_gid)!=(d['uid'],d['gid']):os.chown(p,d['uid'],d['gid'],follow_symlinks=False)
  os.chmod(p,d['mode'],follow_symlinks=False)
  if current_acl!=d['acl']:
   acl=LIB.acl_from_text((d['acl'] or '!#acl 1\n').encode())
   if not acl:raise OSError('Cannot parse restore ACL')
   try:
    if LIB.acl_set_link_np(b,0x100,acl)!=0:raise OSError('Cannot restore ACL')
   finally:LIB.acl_free(acl)
  os.utime(p,ns=(d['mtime_ns'],d['mtime_ns']),follow_symlinks=False)
  os.chflags(p,d['flags'],follow_symlinks=False)
def run(job):
 os.umask(0o077);job=job.resolve(); cfg=json.loads((job/'scope.json').read_text());roots=cfg['roots'];remote=cfg['remote']
 if cfg.get('delete_local') is not False:raise RuntimeError('Must be backup-only')
 lock=open(job/'worker.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 log=job/'worker.log';snapshot=job/'capture';chunks=job/'chunks'
 def state(phase,**kw):save(job/'status.json',dict(phase=phase,pid=os.getpid(),updated_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),**kw))
 try:
  if not (job/'capture-ready.json').exists():
   state('inventory-and-capture')
   before=scan(HOME,roots);save(job/'source-before.json',before)
   total=sum(d.get('size',0) for d in before.values())
   free=os.statvfs(job).f_bavail*os.statvfs(job).f_frsize
   if free<total*3+15*1024**3:raise RuntimeError('Insufficient conservative capture/restore headroom')
   if snapshot.exists():raise RuntimeError('Partial capture exists; inspect before retry')
   snapshot.mkdir()
   for rel in roots:
    dst=snapshot/rel;dst.parent.mkdir(parents=True,exist_ok=True)
    call(['/bin/cp','-cRpP',str(HOME/rel),str(dst)],log)
   # macOS recursive cp skips literal AppleDouble files; copy omitted regular files explicitly.
   for rel,d in before.items():
    dst=snapshot/rel
    if d['kind']=='file' and not dst.exists():
     call(['/bin/cp','-cpP',str(HOME/rel),str(dst)],log)
   # Reconstruct hardlink groups lost by cp, only within this declared scope.
   groups={}
   for rel,d in before.items():
    if d['kind']=='file' and d['nlink']>1:
     key=(d['dev'],d['inode'])
     if key in groups:
      (snapshot/rel).unlink();os.link(snapshot/groups[key],snapshot/rel)
     else:groups[key]=rel
   for rel,d in before.items():
    if d['acl']:
     acl=LIB.acl_from_text(d['acl'].encode())
     if not acl:raise OSError('ACL parse failed')
     try:
      if LIB.acl_set_link_np(os.fsencode(snapshot/rel),0x100,acl)!=0:raise OSError('ACL capture failed')
     finally:LIB.acl_free(acl)
   for rel,d in before.items():
    if d['kind']=='dir':os.utime(snapshot/rel,ns=(d['mtime_ns'],d['mtime_ns']),follow_symlinks=False)
   after=scan(HOME,roots)
   if before!=after:raise RuntimeError('Source changed during capture; preserve incomplete capture')
   state('hashing-capture',source_bytes=total)
   captured=scan(snapshot,roots,True);same(before,captured)
   if before!=scan(HOME,roots):raise RuntimeError('Source changed during capture verification')
   save(job/'captured-manifest.json',captured);save(job/'capture-ready.json',dict(source_bytes=total,files=sum(d['kind']=='file' for d in before.values()),source_stable_during_capture=True,atomic_filesystem_snapshot=False))
  if not (job/'chunks-ready.json').exists():
   state('building-archive')
   if chunks.exists():raise RuntimeError('Partial chunks exist; inspect before retry')
   parts=tar_chunks(snapshot,roots,chunks,log);save(job/'chunks-ready.json',parts)
  parts=json.loads((job/'chunks-ready.json').read_text())
  state('uploading',archive_bytes=sum(p['size'] for p in parts))
  rc(['copy',str(chunks),remote+'/chunks','--immutable','--checksum','--transfers','4','--stats','30s','--use-json-log','--log-file',str(job/'upload.log')],log)
  state('verifying-all-remote-bytes')
  rc(['check',str(chunks),remote+'/chunks','--download','--one-way','--combined',str(job/'remote-check.txt')],log)
  state('full-restore-test')
  restored=job/'restore-test'
  if not (job/'restore-ready.json').exists():
   if restored.exists():raise RuntimeError('Partial restore exists; inspect before retry')
   extract(chunks,parts,restored,log)
   captured=json.loads((job/'captured-manifest.json').read_text()); restore_metadata(restored,captured); recovered=scan(restored,roots,True);same(captured,recovered,True)
   save(job/'restore-ready.json',dict(all_file_hashes_match=True,all_portable_metadata_match=True))
  state('saving-receipt')
  # Later edits are retained; backup represents captured state, not a live mirror.
  before=json.loads((job/'source-before.json').read_text());current=scan(HOME,roots)
  changed=[p for p in set(before)|set(current) if before.get(p)!=current.get(p)]
  save(job/'source-changes-after-capture.json',changed)
  for name in ['scope.json','source-before.json','captured-manifest.json','chunks-ready.json','capture-ready.json','restore-ready.json','source-changes-after-capture.json','RESTORE.md','backup.py']:
   rc(['copyto',str(job/name),remote+'/'+name,'--immutable','--checksum'],log)
  rc(['lsjson',remote,'--recursive','--hash'],job/'remote-objects.json')
  receipt=dict(completed_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),remote=remote,source_roots=roots,local_originals_retained=True,remote_download_check='passed all archive bytes',restore='all content SHA256 and portable metadata matched',changes_since_capture=len(changed),capture=json.loads((job/'capture-ready.json').read_text()),temporary_local_data_retained=True)
  save(job/'complete.json',receipt);rc(['copyto',str(job/'complete.json'),remote+'/complete.json','--immutable'],log)
  state('complete',**receipt)
 except Exception as e:
  state('blocked',error=str(e));raise
if __name__=='__main__':run(Path(sys.argv[1]))
