"""Advisory duplicate/variant hints. Never equate a near match with identical weights."""
import json
import re
from pathlib import Path
import vault


def identity(model):
    return (model['repo'].lower(),model['revision'],tuple(sorted((f['name'],f['size']) for f in model.get('files',[]))))


def family(repo):
    name=repo.split('/')[-1].lower()
    versions=set(re.findall(r'(?:qwen|llama|gemma|mistral|deepseek|phi)[-_. ]*\d+(?:\.\d+)?',name))
    versions={re.sub(r'[-_ ]','',v) for v in versions}
    sizes=set(re.findall(r'(?<![\d.])\d+(?:\.\d+)?b\b',name))
    words=set(re.findall(r'[a-z]+[0-9.]*',name)) - {'gguf','instruct','it','abliterated','uncensored','heretic','edition','native','safetensors','model'}
    return versions,sizes,words


def hints(candidate,known,root):
    result=[];seen=set();target=identity(candidate)
    cv,cs,cw=family(candidate['repo'])
    for model in known:
        try:
            key=identity(model)
            if key in seen:continue
            seen.add(key)
            exact=key==target
            same_repo=model['repo'].lower()==candidate['repo'].lower()
            mv,ms,mw=family(model['repo'])
            family_match=bool(cv & mv)
            name_match=len(cw & mw)>=2 and len(cw & mw)/max(1,min(len(cw),len(mw)))>=.75
            if not (exact or same_repo or family_match or name_match):continue
            base=root/'models'/vault.safe(model['repo'])/vault.safe(model['revision'])
            present=bool(model.get('files'))
            for f in model.get('files',[]):
                path=base/vault.safe(f['name'])
                if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe match path')
                present=present and path.is_file() and path.stat().st_size==f['size']
            queued=model.get('_queued',False)
            # Old plans with no files on disk and no live queue entry are not useful matches.
            if not queued and not present:continue
            if exact:reason='Same repository, revision and selected files'
            elif same_repo:reason='Same repository; different revision or file/quantization selection'
            elif family_match:
                reason='Same model family/version'
                if cs and ms:reason+=' and parameter size' if cs & ms else '; different parameter size'
                reason+='; publisher, tuning or quantization may differ'
            else:reason='Similar repository name; lineage is not confirmed'
            result.append(dict(kind='already_downloaded' if exact and present else 'already_queued' if exact and queued else 'possible_match',
                repo=model['repo'],revision=model['revision'],reason=reason,
                location=str(base) if present else None,downloaded=present,queued=queued,
                size=sum(f['size'] for f in model.get('files',[]))))
        except (OSError,ValueError,KeyError,TypeError):continue
    result.sort(key=lambda r:(r['kind']=='possible_match',not r['downloaded'],r['repo']))
    return result[:8]


def check(app,cfg,candidate,store=None):
    try:
        vault.guard(cfg);root=Path(cfg['volume'])/'ModelVault';known=[]
        for m in vault.read(root/'plan.json',{}).get('items',[]):known.append({**m,'_queued':True})
        for folder in ('specific-plans','queue-history'):
            for path in (app/folder).glob('*.json'):
                try:known.extend(vault.read(path,{}).get('items',[]))
                except (OSError,ValueError):continue
        if store:
            with store.connect() as db:
                for row in db.execute('SELECT snapshot FROM plans'):
                    data=json.loads(row[0])
                    if data.get('volume')==cfg['volume']:known.extend(data.get('items',[]))
        return dict(available=True,matches=hints(candidate,known,root))
    except (OSError,ValueError,RuntimeError,KeyError):
        return dict(available=False,matches=[])
