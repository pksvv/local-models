#!/usr/bin/env python3
"""Model Vault: checkpointed Hugging Face downloads. Python 3.10+, macOS."""
import argparse, errno, fcntl, getpass, hashlib, json, os, plistlib, re, shutil
import subprocess, sys, time, uuid
from pathlib import Path
from urllib.parse import quote
import requests

APP = Path(__file__).resolve().parent
CONFIG = Path.home()/'.config/model-vault/config.json'
GIB = 1024**3
CHECKPOINT_BYTES = 64*1024**2
CHECKPOINT_SECONDS = 15


def sync_data(fd):
    os.fsync(fd)
    if sys.platform == 'darwin':
        try: fcntl.fcntl(fd, getattr(fcntl, 'F_FULLFSYNC', 51))
        except OSError as e:
            if e.errno not in (errno.EINVAL, errno.ENOTSUP): raise
            # Some USB/filesystem combinations cannot flush the device cache.


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w') as f:
        json.dump(data, f, indent=2); f.write('\n'); f.flush(); sync_data(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def read(path, default=None):
    p=Path(path)
    return json.loads(p.read_text()) if p.exists() else default


def volume_info(volume):
    if sys.platform != 'darwin': raise RuntimeError('Drive setup requires macOS.')
    p=subprocess.run(['/usr/sbin/diskutil','info','-plist',str(volume)],capture_output=True,check=True)
    return plistlib.loads(p.stdout)


def guard(cfg):
    volume=Path(cfg['volume'])
    if not os.path.ismount(volume): raise RuntimeError('Waiting for mounted external drive volume.')
    marker=volume/'ModelVault'/'.volume-id'
    if not marker.is_file() or marker.read_text().strip()!=cfg['marker']:
        raise RuntimeError('Drive identity missing or different; no writes allowed.')
    if cfg.get('device') is not None and volume.stat().st_dev!=cfg['device']:
        raise RuntimeError('Volume changed during this run; restart to recheck identity.')


def token():
    return os.environ.get('HF_TOKEN') or read(CONFIG,{}).get('token')


def api(path, params=None):
    headers={'Authorization':'Bearer '+token()} if token() else {}
    r=requests.get('https://huggingface.co/api/'+path,headers=headers,params=params,timeout=(20,60))
    r.raise_for_status(); return r.json()


def safe(name):
    p=Path(name)
    if p.is_absolute() or '..' in p.parts: raise ValueError('Unsafe remote path')
    return p


def select(row, siblings):
    docs=[]; weights=[]
    for f in siblings:
        n=f['rfilename']; safe(n); low=n.lower()
        if low.endswith(('.md','.txt','.json','.jinja','.model','.tiktoken')) or Path(low).name.startswith(('license','notice')):
            docs.append(f)
        elif row['format']=='gguf' and low.endswith('.gguf'):
            if row.get('quant','Q4_K_M').upper() in n.upper(): weights.append(f)
        elif row['format']=='native' and low.endswith('.safetensors'): weights.append(f)
        elif row['format']=='native_bin' and n in row.get('weight_files',[]): weights.append(f)
    if row['format']=='gguf':
        # Repositories sometimes contain both a single file and its split copy.
        names={f['rfilename'] for f in weights}
        weights=[f for f in weights if re.sub(r'-\d{5}-of-\d{5}(?=\.gguf$)', '', f['rfilename'], flags=re.I) not in names
                 or not re.search(r'-\d{5}-of-\d{5}\.gguf$', f['rfilename'], re.I)]
    if not weights: raise ValueError('No selected weights; adjust format/quant in catalog.json')
    # Include exactly one preferred vision projector, if the repository publishes one.
    projectors=[f for f in siblings if 'mmproj' in f['rfilename'].lower() and f['rfilename'].lower().endswith('.gguf')]
    if projectors:
        projectors.sort(key=lambda f: (not ('f16' in f['rfilename'].lower() or 'bf16' in f['rfilename'].lower()),f['rfilename']))
        docs.append(projectors[0])
    selected={f['rfilename']:f for f in docs+weights}
    result=[]
    for n,f in selected.items():
        if f.get('size') is None: raise ValueError('Missing remote size: '+n)
        lfs=f.get('lfs') or {}
        result.append(dict(name=n,size=f['size'],sha256=lfs.get('sha256'),git_sha1=None if lfs else f.get('blobId')))
    return result


def make_plan(cfg):
    guard(cfg)
    rows=read(APP/'catalog.json'); items=[]; errors=[]
    for row in rows:
        if not row['enabled']: continue
        try:
            d=api('models/'+row['repo'],{'blobs':'true'})
            files=select(row,d['siblings'])
            item=dict(repo=d['id'],revision=d['sha'],category=row['category'],license=d.get('cardData',{}).get('license'),gated=d.get('gated'),files=files)
            items.append(item)
            guard(cfg); atomic(Path('metadata')/(d['id'].replace('/','--')+'.json'),d)
            print(d['id'],round(sum(f['size'] for f in files)/GIB,2),'GiB',flush=True)
        except Exception as e:
            errors.append({'repo':row['repo'],'error':str(e)});print('PLAN ERROR',row['repo'],str(e),flush=True)
    if errors:
        atomic('plan-errors.json',errors)
        raise RuntimeError('Plan has errors; prior plan preserved. Fix catalog/access and run plan again.')
    if not items:raise RuntimeError('No enabled models.')
    plan=dict(created=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),items=items,total_bytes=sum(f['size'] for m in items for f in m['files']))
    guard(cfg); atomic('plan.json',plan)
    print('Pinned plan:',round(plan['total_bytes']/GIB,2),'GiB. Run start after review.')
    return plan


def valid(path, item):
    if not path.is_file() or path.stat().st_size!=item['size']:return False
    algo='sha256' if item.get('sha256') else 'sha1'
    expected=item.get('sha256') or item.get('git_sha1')
    if not expected:raise ValueError('No upstream checksum; refusing unverified completion: '+item['name'])
    h=hashlib.new(algo)
    if algo=='sha1':h.update(('blob '+str(item['size'])+'\0').encode())
    with path.open('rb') as f:
        while b:=f.read(8*1024**2): h.update(b)
    return h.hexdigest()==expected


def download(url, dest, item, check=lambda:None, reserve=20*GIB, headers=None):
    """Durable offset advances only after fsync(data), then fsync(checkpoint)."""
    check(); dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
    part=dest.with_name(dest.name+'.part'); cp=dest.with_name(dest.name+'.checkpoint.json')
    if valid(dest,item):return 'existing'
    if dest.exists():
        # Corrupt completed data is not trusted. Re-download into .part; replace only after verification.
        print('Re-downloading invalid file:',dest,flush=True)
    state=read(cp,{})
    fingerprint=[url,item['size'],item.get('sha256'),item.get('git_sha1')]
    offset=state.get('offset',0) if state.get('fingerprint')==fingerprint else 0
    if not part.exists() or part.stat().st_size<offset:offset=0
    if not 0<=offset<=item['size']:offset=0
    with part.open('r+b' if part.exists() else 'w+b') as f:
        f.truncate(offset);f.flush();sync_data(f.fileno())
    if offset==item['size']:
        if valid(part,item):
            check();os.replace(part,dest)
            fd=os.open(dest.parent,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
            cp.unlink(missing_ok=True);return 'verified partial'
        offset=0
        with part.open('wb') as f:f.flush();sync_data(f.fileno())
    if shutil.disk_usage(dest.parent).free < (item['size']-offset)+reserve:
        raise RuntimeError('Space reserve reached; free space or disable larger models.')
    hdr=dict(headers or {})
    hdr['Accept-Encoding']='identity'
    if offset:hdr['Range']='bytes='+str(offset)+'-'
    with requests.get(url,headers=hdr,stream=True,timeout=(20,60)) as response:
        response.raise_for_status()
        if offset and response.status_code==200:offset=0
        elif response.status_code==206:
            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
            if not match or int(match[1])!=offset or int(match[3])!=item['size']:
                raise RuntimeError('Invalid HTTP range response')
        elif response.status_code!=200:raise RuntimeError('Unexpected HTTP status')
        with part.open('r+b') as f:
            f.truncate(offset);f.seek(offset)
            last=offset;last_time=time.monotonic()
            def checkpoint():
                check();f.flush();sync_data(f.fileno())
                atomic(cp,dict(offset=f.tell(),fingerprint=fingerprint,updated=time.time()))
            checkpoint()
            try:
                for b in response.iter_content(chunk_size=1024**2):
                    if not b:continue
                    check()
                    if shutil.disk_usage(dest.parent).free < reserve+len(b):raise RuntimeError('Space reserve reached')
                    if f.tell()+len(b)>item['size']:raise RuntimeError('Response exceeds expected size')
                    f.write(b)
                    if f.tell()-last>=CHECKPOINT_BYTES or time.monotonic()-last_time>=CHECKPOINT_SECONDS:
                        checkpoint();last=f.tell();last_time=time.monotonic()
                        print(f'{dest.name}: {last/item["size"]:.1%} durable',flush=True)
            finally:
                checkpoint()
    if not valid(part,item):
        if part.stat().st_size==item['size']:
            atomic(cp,dict(offset=0,fingerprint=fingerprint,updated=time.time()))
        raise RuntimeError('Incomplete file or checksum mismatch; queued for retry.')
    check();os.replace(part,dest)
    fd=os.open(dest.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    cp.unlink(missing_ok=True)
    return 'downloaded + verified'


def run(cfg, verify_only=False, plan_path='plan.json'):
    plan=read(plan_path)
    if not plan:raise RuntimeError('Run plan first.')
    state=read('status.json',{})
    errors=0
    for m in plan['items']:
        base=Path('models')/m['repo']/m['revision']
        for f in m['files']:
            guard(cfg);dest=base/safe(f['name']);key=str(dest)
            # Recheck hash after each restart. Slow on HDD, but detects cut-related corruption.
            try:
                if verify_only:
                    result='verified' if valid(dest,f) else 'missing or corrupt'
                    if result!='verified':errors+=1
                else:
                    url='https://huggingface.co/'+m['repo']+'/resolve/'+m['revision']+'/'+quote(f['name'],safe='/')
                    result=download(url,dest,f,lambda:guard(cfg),cfg['reserve_gib']*GIB,{'Authorization':'Bearer '+token()} if token() else {})
                state[key]={'status':result,'time':time.time(),'bytes':f['size']}
                print(result,key,flush=True)
            except (requests.RequestException,OSError,RuntimeError,ValueError) as e:
                errors+=1;state[key]={'status':'retry required','error':str(e),'time':time.time()}
                print('RETRY REQUIRED',key,str(e),flush=True)
            guard(cfg);atomic('status.json',state)
    return errors


def setup(args):
    v=Path(args.volume).expanduser().resolve()
    if not os.path.ismount(v) or v.parent!=Path('/Volumes'):raise RuntimeError('Specify a mounted external volume under /Volumes.')
    info=volume_info(v)
    if info.get('Internal',False):raise RuntimeError('Refusing internal disk.')
    if not info.get('Writable',True):raise RuntimeError('Drive is read-only.')
    root=v/'ModelVault';root.mkdir(exist_ok=True)
    marker=root/'.volume-id'
    if not marker.exists():
        with marker.open('x') as f:f.write(str(uuid.uuid4()));f.flush();sync_data(f.fileno())
    old=read(CONFIG,{})
    cfg=dict(volume=str(v),marker=marker.read_text().strip(),reserve_gib=args.reserve,token=old.get('token'))
    CONFIG.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Config contains a token only after explicit login; protect before writing.
    os.umask(0o077);atomic(CONFIG,cfg);CONFIG.chmod(0o600)
    print('Configured',root,'— existing drive contents preserved. Run plan next.')


def install_agent():
    uid=os.getuid();label='com.vipul.model-vault'
    path=Path.home()/'Library/LaunchAgents'/f'{label}.plist'
    log=Path.home()/'Library/Logs/ModelVault';log.mkdir(parents=True,exist_ok=True)
    data={'Label':label,'ProgramArguments':['/usr/bin/caffeinate','-i',sys.executable,str(APP/'vault.py'),'watch'],
          'RunAtLoad':True,'StartInterval':120,'ProcessType':'Background',
          'StandardOutPath':str(log/'manager.log'),'StandardErrorPath':str(log/'manager-error.log')}
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(plistlib.dumps(data))
    subprocess.run(['launchctl','bootout',f'gui/{uid}',str(path)],capture_output=True)
    subprocess.run(['launchctl','bootstrap',f'gui/{uid}',str(path)],check=True)
    print('Installed login agent. Logs:',log)


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['setup','login','plan','start','watch','verify','status','install-agent','remove-agent','discover'])
    p.add_argument('--volume');p.add_argument('--reserve',type=int,default=20);p.add_argument('--search',default='abliterated');p.add_argument('--limit',type=int,default=100)
    p.add_argument('--plan-file',default='plan.json',help='Explicit pinned plan; custom plans do not change the main queue')
    p.add_argument('--expected-plan',help='Refuse a changed queue after dashboard review')
    a=p.parse_args()
    if a.command=='setup':
        if not a.volume:p.error('--volume required')
        if a.reserve<5:p.error('reserve must be at least 5 GiB')
        setup(a);return
    if a.command=='login':
        cfg=read(CONFIG)
        if not cfg:raise RuntimeError('Run setup first')
        value=getpass.getpass('HF read token (hidden; empty cancels): ').strip()
        if not value:return
        os.umask(0o077);cfg['token']=value;atomic(CONFIG,cfg);CONFIG.chmod(0o600);return
    if a.command=='install-agent':install_agent();return
    if a.command=='remove-agent':
        path=Path.home()/'Library/LaunchAgents/com.vipul.model-vault.plist'
        subprocess.run(['launchctl','bootout',f'gui/{os.getuid()}',str(path)],capture_output=True);path.unlink(missing_ok=True);return
    cfg=read(CONFIG)
    if not cfg:raise RuntimeError('Run setup first.')
    guard(cfg);cfg['device']=Path(cfg['volume']).stat().st_dev
    os.chdir(Path(cfg['volume'])/'ModelVault')
    # Keep a cwd on the mounted filesystem: an unplug cannot redirect relative writes to the internal disk.
    with open('.manager.lock','a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another manager is active.')
        if a.expected_plan:
            signature=hashlib.sha256(Path(a.plan_file).read_bytes()).hexdigest()
            if signature!=a.expected_plan:raise RuntimeError('Plan changed after review; review the queue again.')
        if a.command=='plan':make_plan(cfg)
        elif a.command=='discover':
            candidates=api('models',{'search':a.search,'limit':a.limit,'sort':'downloads','direction':-1})
            atomic('discovered-candidates.json',candidates);print('Saved candidates for manual review; no downloads enabled.')
        elif a.command=='status':
            state=read('status.json',{});print(json.dumps(state,indent=2))
        else:
            signature=hashlib.sha256(Path(a.plan_file).read_bytes()).hexdigest()
            boot=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.boottime'],text=True).strip() if sys.platform=='darwin' else 'test'
            done=read('completed.json',{})
            if a.command=='watch' and done.get('plan')==signature and done.get('boot')==boot:
                return
            errors=run(cfg,a.command=='verify',a.plan_file)
            if errors:raise RuntimeError(str(errors)+' files need attention; retry on next launch.')
            guard(cfg)
            if a.plan_file=='plan.json':atomic('completed.json',dict(plan=signature,boot=boot,time=time.time()))
            print('Queue complete. All files verified; no repeated transfers this boot.')

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nStopped. Durable checkpoints retained.');sys.exit(130)
    except Exception as e:print(type(e).__name__+': '+str(e),file=sys.stderr);sys.exit(1)
