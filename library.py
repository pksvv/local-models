"""Read-only inventory of complete model selections from known pinned plans."""
import hashlib
import json
from pathlib import Path
import vault

VERIFIED = {'verified', 'existing', 'downloaded + verified', 'verified partial'}


def inventory(cfg, plans, cached=False):
    if cached:
        return dict(available=False, models=[], error='Drive unavailable; library cannot be checked live.')
    try:
        vault.guard(cfg)
        root=Path(cfg['volume'])/'ModelVault'
        status=vault.read(root/'status.json',{})
        models=[];seen=set()
        for plan in plans:
            for model in plan.get('items',[]):
                files=model.get('files',[])
                key=(model['repo'],model['revision'],tuple(sorted((f['name'],f['size']) for f in files)))
                if key in seen or not files:continue
                seen.add(key)
                base=root/'models'/vault.safe(model['repo'])/vault.safe(model['revision'])
                verified=True;dates=[]
                for item in files:
                    dest=base/vault.safe(item['name'])
                    if not dest.resolve().is_relative_to(root.resolve()):raise ValueError('Library path escapes vault')
                    if not dest.is_file() or dest.stat().st_size!=item['size']:break
                    record=status.get(str(dest.relative_to(root)),{})
                    verified=verified and record.get('status') in VERIFIED
                    if record.get('time'):dates.append(record['time'])
                else:
                    models.append(dict(id=hashlib.sha256(repr(key).encode()).hexdigest()[:16],
                        repo=model['repo'],revision=model['revision'],category=model.get('category','Uncategorized'),
                        size=sum(f['size'] for f in files),files=len(files),location=str(base),
                        verification='Previously verified' if verified else 'Verification pending',
                        last_checked=max(dates) if dates else None))
        return dict(available=True,models=models,error=None)
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        return dict(available=False,models=[],error=str(exc))
