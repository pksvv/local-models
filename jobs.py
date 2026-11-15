"""Persistent dashboard job metadata and bounded structured log reads."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid
import vault


def create(root, action, signature):
    key = datetime.now(timezone.utc).strftime('job-%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8]
    directory = Path(root) / 'job-logs'
    directory.mkdir(exist_ok=True)
    name = 'Download main queue' if action == 'start' else 'Verify main queue' if action == 'verify' else 'Download ' + action.removeprefix('specific: ')
    data = dict(id=key, name=name, description='Checksum audit; no transfers' if action=='verify' else 'Pinned model transfer with durable checkpoint recovery',
                action=action, signature=signature, status='starting', started=time.time(), ended=None, exit_code=None)
    vault.atomic(directory / (key+'.json'), data)
    return data, directory / (key+'.jsonl')


def update(root, data, **fields):
    data.update(fields)
    vault.atomic(Path(root) / 'job-logs' / (data['id']+'.json'), data)


def records(path):
    if not path.exists(): return []
    with path.open('rb') as f:
        f.seek(max(0, path.stat().st_size - 128000))
        lines=f.read().decode(errors='replace').splitlines()
    result=[]
    for line in lines:
        try:
            value=json.loads(line)
            if isinstance(value,dict) and 'timestamp' in value:result.append(value)
        except ValueError:pass
    return result[-200:]


def history(root):
    directory=Path(root)/'job-logs'
    result=[]
    for path in sorted(directory.glob('*.json'), reverse=True)[:30]:
        try:
            data=json.loads(path.read_text())
            logs=records(path.with_suffix('.jsonl'))
            final=next((r for r in reversed(logs) if r.get('event')=='job_finished'),None)
            if final and final.get('status'):data['status']=final['status']
            if not final and data.get('status') in ('starting','running') and data.get('pid'):
                try:os.kill(data['pid'], 0)
                except ProcessLookupError:data['status']='interrupted'
                except PermissionError:data['status']='unknown'
            data['last_activity']=logs[-1]['timestamp'] if logs else None
            data['elapsed_seconds']=max(0,(data.get('ended') or time.time())-data['started'])
            data['current_file']=next((r.get('file') for r in reversed(logs) if r.get('file')),None)
            data['progress']=next((r for r in reversed(logs) if r.get('event')=='progress' and r.get('file')==Path(data['current_file'] or '').name),None)
            data['logs']=logs
            result.append(data)
        except (ValueError,OSError,KeyError):continue
    return result
