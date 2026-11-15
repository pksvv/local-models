#!/usr/bin/env python3
"""Local Model Vault 2.0 dashboard. Opening it never starts downloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import vault
from queue_store import QueueStore

APP = Path(__file__).resolve().parent


def tags_for(model):
    category = (model.get('category') or '').lower()
    tags = []
    for word, label in [('abliterated', 'Abliterated'), ('uncensored', 'Uncensored'),
                        ('general', 'General'), ('reasoning', 'Reasoning'),
                        ('coding', 'Coding'), ('vision', 'Vision'),
                        ('embedding', 'Embedding'), ('rerank', 'Reranking'), ('speech', 'Speech')]:
        if word in category:
            tags.append(label)
    return tags or [model.get('category') or 'Uncategorized']


def snapshot():
    cfg = vault.read(vault.CONFIG, {})
    result = dict(ready=False, error=None, volume=cfg.get('volume'),
                  reserve_gib=cfg.get('reserve_gib', 20), items=[], total_bytes=0,
                  durable_bytes=0, completed_bytes=0, signature=None)
    result['catalog'] = vault.read(APP / 'catalog.json', [])
    if not cfg:
        result['error'] = 'Drive not configured. Run vault.py setup first.'
        return result
    try:
        vault.guard(cfg)
        root = Path(cfg['volume']) / 'ModelVault'
        usage = vault.shutil.disk_usage(root)
        result.update(free_bytes=usage.free, disk_bytes=usage.total)
        plan_path = root / 'plan.json'
        if not plan_path.exists():
            raise RuntimeError('No pinned plan. Run vault.py plan, then review the queue here.')
        raw = plan_path.read_bytes()
        plan = json.loads(raw)
        result.update(signature=hashlib.sha256(raw).hexdigest(), created=plan.get('created'))
        state = vault.read(root / 'status.json', {})
        for model in plan['items']:
            base = root / 'models' / vault.safe(model['repo']) / vault.safe(model['revision'])
            entry = {k: model.get(k) for k in ('repo', 'revision', 'category', 'license', 'gated')}
            entry['tags'] = tags_for(model)
            entry['publisher'] = model['repo'].split('/')[0]
            catalog_row = next((r for r in result['catalog'] if r['repo'] == model['repo']), {})
            entry['format'] = catalog_row.get('format', 'unknown').upper()
            entry['files'] = []
            for item in model['files']:
                dest = base / vault.safe(item['name'])
                # Refuse reads through paths escaping the vault, including symlinks.
                if not dest.resolve().is_relative_to(root.resolve()):
                    raise ValueError('File path escapes the vault')
                status = state.get(str(dest.relative_to(root)), {})
                cp = vault.read(dest.with_name(dest.name + '.checkpoint.json'), {})
                part = dest.with_name(dest.name + '.part')
                url = 'https://huggingface.co/' + model['repo'] + '/resolve/' + model['revision'] + '/' + vault.quote(item['name'], safe='/')
                fingerprint = [url, item['size'], item.get('sha256'), item.get('git_sha1')]
                durable = cp.get('offset', 0) if cp.get('fingerprint') == fingerprint else 0
                durable = durable if isinstance(durable, int) and 0 <= durable <= item['size'] and part.exists() and part.stat().st_size >= durable else 0
                present = dest.is_file() and dest.stat().st_size == item['size']
                # Status is historical: no expensive checksum pass on each poll.
                label = status.get('status', 'queued')
                if not present and label in ('verified', 'existing', 'downloaded + verified', 'verified partial'):
                    label = 'missing'
                if present and label == 'queued':
                    label = 'present; verification pending'
                file = dict(name=item['name'], size=item['size'], durable_bytes=durable,
                            present=present, status=label, error=status.get('error'))
                entry['files'].append(file)
                result['total_bytes'] += item['size']
                result['durable_bytes'] += durable
                if present:
                    result['completed_bytes'] += item['size']
            files = entry['files']
            entry['download_status'] = ('Needs attention' if any(f['error'] or f['status'] in ('retry required', 'missing or corrupt', 'missing') for f in files)
                else 'Downloaded' if files and all(f['present'] for f in files)
                else 'Partial' if any(f['present'] or f['durable_bytes'] for f in files)
                else 'Queued')
            result['items'].append(entry)
        result['ready'] = True
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        result['error'] = str(exc)
    return result


class Controller:
    def __init__(self, store=None):
        self.store = store
        self.event_id = None
        self.lock = threading.Lock()
        self.process = None
        self.action = None
        self.log = APP / 'dashboard-manager.log'

    def snapshot(self):
        data = snapshot()
        if self.store:
            self.store.sync(data)
            if not data['ready']:
                saved = self.store.latest(data.get('volume'))
                if saved:
                    data.update(saved)
                    data['cached'] = True
        return data

    def state(self):
        with self.lock:
            if self.event_id and self.process is not None and self.process.poll() is not None:
                self.store.finish(self.event_id, 'exited: ' + str(self.process.returncode))
                self.event_id = None
            return dict(running=self.process is not None and self.process.poll() is None,
                        action=self.action, exit_code=self.process.poll() if self.process else None)

    def start(self, signature, action):
        if action not in ('start', 'verify'):
            raise ValueError('Unsupported action')
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                raise ValueError('A dashboard worker is already active')
            current = snapshot()
            if not current['ready'] or signature != current['signature']:
                raise ValueError('Queue unavailable or changed. Refresh and review it again.')
            if action == 'verify' and not any(f['present'] for m in current['items'] for f in m['files']):
                raise ValueError('No downloaded files to verify. Download files first.')
            # The CLI retains exclusive manager locking, volume guards, and cwd on disk.
            with self.log.open('ab') as log:
                self.process = subprocess.Popen(
                    [sys.executable, '-u', str(APP / 'vault.py'), action,
                     '--expected-plan', signature], cwd=APP, stdout=log, stderr=log,
                    start_new_session=True)
            self.action = action
            if self.store:
                self.event_id = self.store.event(action, signature, self.process.pid, 'started')

    def stop(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.process.send_signal(signal.SIGINT)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, data, mime='application/json'):
        body = json.dumps(data).encode() if mime == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def trusted_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def do_GET(self):
        if not self.trusted_host():
            return self.respond(403, {'error': 'Invalid host'})
        if self.path == '/api/status':
            data = self.server.controller.snapshot()
            data.update(worker=self.server.controller.state(), csrf=self.server.csrf)
            return self.respond(200, data)
        if self.path == '/api/log':
            p = self.server.controller.log
            if p.exists():
                with p.open('rb') as f:
                    f.seek(max(0, p.stat().st_size - 16000))
                    value = f.read().decode(errors='replace')
            else:
                value = 'No dashboard worker has run.'
            return self.respond(200, {'text': value})
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/help': ('help.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/language.js': ('language.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if self.path in assets:
            name, mime = assets[self.path]
            return self.respond(200, (APP / 'web' / name).read_bytes(), mime)
        self.respond(404, {'error': 'Not found'})

    def do_POST(self):
        if not self.trusted_host() or self.headers.get('X-CSRF-Token') != self.server.csrf:
            return self.respond(403, {'error': 'Invalid request token'})
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            return self.respond(403, {'error': 'Invalid origin'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096:
                raise ValueError('Invalid body length')
            data = json.loads(self.rfile.read(size))
            if self.path == '/api/stop':
                self.server.controller.stop()
            elif self.path in ('/api/start', '/api/verify'):
                if data.get('reviewed') is not True:
                    raise ValueError('Review the queue before proceeding')
                self.server.controller.start(data.get('signature'), self.path.rsplit('/', 1)[1])
            else:
                return self.respond(404, {'error': 'Not found'})
            self.respond(200, {'ok': True})
        except (ValueError, OSError) as exc:
            self.respond(409, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.controller = Controller(QueueStore(APP / 'queue.sqlite3'))
    server.csrf = secrets.token_urlsafe(32)
    print(f'Model Vault 2.0: http://127.0.0.1:{server.server_port} (downloads idle)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.controller.stop()
        if server.controller.process is not None:
            try:
                server.controller.process.wait(timeout=65)
            except subprocess.TimeoutExpired:
                print('Worker is still stopping; durable checkpoints remain on disk.', flush=True)
        server.server_close()


if __name__ == '__main__':
    main()
