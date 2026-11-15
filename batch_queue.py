"""Direct repository-link preview and reviewed queue append, without web research."""
import re
import secrets
from urllib.parse import urlparse
import vault
from research import Research

CATEGORIES=('General','Abliterated','Uncensored','Coding','Reasoning','Vision','Embedding','Reranking','Speech')


def repos(text):
    if not isinstance(text,str) or len(text)>3500:raise ValueError('Paste up to 10 repository links, one per line')
    result=[]
    for line in text.splitlines():
        value=line.strip()
        if not value:continue
        if value.startswith('https://'):
            url=urlparse(value)
            if url.netloc!='huggingface.co':raise ValueError('Only Hugging Face repository page links are supported')
            value=url.path.strip('/') # Tracking parameters do not identify a different repository.
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*',value):raise ValueError('Use repository page links or owner/repo, one per line')
        if value.lower() not in [r.lower() for r in result]:result.append(value)
    if not 1<=len(result)<=10:raise ValueError('Paste 1–10 different repositories')
    return result


def preview(root,controller,data):
    entries=repos(data.get('links'))
    mode=data.get('format','auto');quant=str(data.get('quant','Q4_K_M')).strip()
    if mode not in ('auto','gguf','native'):raise ValueError('Choose Auto, GGUF, or native')
    rows=[]
    for repo in entries:
        try:
            fmt=mode
            if mode=='auto':
                remote=vault.api('models/'+repo,{'blobs':'true'})
                fmt='gguf' if any(f['rfilename'].lower().endswith('.gguf') and 'mmproj' not in f['rfilename'].lower() for f in remote['siblings']) else 'native'
            value=controller.preview_model(dict(repo=repo,format=fmt,quant=quant,category='General'))
            with controller.lock:controller.previews.pop(value['preview'],None)
            rows.append(dict(repo=repo,status='validated',plan=value['plan'],format=fmt))
        except (OSError,ValueError,RuntimeError,KeyError,vault.requests.RequestException) as exc:
            rows.append(dict(repo=repo,status='unavailable',error=str(exc)))
    key=secrets.token_urlsafe(24)
    vault.atomic(root/'batch-previews'/(key+'.json'),dict(status='completed',candidates=rows))
    return dict(batch=key,rows=rows,total_bytes=sum(r['plan']['total_bytes'] for r in rows if r['status']=='validated'))


def enqueue(root,data):
    key=data.get('batch','')
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}',key):raise ValueError('Preview the links first')
    worker=Research(root,None);worker.path=root/'batch-previews'/(key+'.json')
    saved=vault.read(worker.path)
    if not saved:raise ValueError('Batch preview not found; preview again')
    categories=data.get('categories',{})
    if not isinstance(categories,dict):raise ValueError('Invalid category selections')
    for index,value in categories.items():
        if value not in CATEGORIES or not index.isdigit() or int(index)>=len(saved['candidates']):raise ValueError('Invalid category')
        row=saved['candidates'][int(index)]
        if row.get('plan'):row['plan']['items'][0]['category']=value
    vault.atomic(worker.path,saved)
    return worker.enqueue(data.get('indices'),data.get('signature'),data.get('budget_gib'))
