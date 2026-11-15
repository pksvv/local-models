"""Durable local queue index; external plan/checkpoints remain authoritative."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time


class QueueStore:
    def __init__(self, path):
        self.path = Path(path)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS plans (
                    signature TEXT PRIMARY KEY, snapshot TEXT NOT NULL, updated REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, action TEXT NOT NULL,
                    signature TEXT, pid INTEGER, outcome TEXT NOT NULL, created REAL NOT NULL
                );
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def sync(self, state):
        if not state.get('ready'):
            return
        payload = {k: state.get(k) for k in ('signature', 'items', 'total_bytes', 'completed_bytes',
                   'durable_bytes', 'created', 'volume', 'reserve_gib')}
        value = json.dumps(payload, sort_keys=True)
        with self.connect() as db:
            row = db.execute('SELECT snapshot FROM plans WHERE signature=?', (state['signature'],)).fetchone()
            if not row or row[0] != value:
                db.execute('INSERT OR REPLACE INTO plans VALUES (?, ?, ?)',
                           (state['signature'], value, time.time()))

    def latest(self, volume):
        with self.connect() as db:
            row = db.execute('SELECT snapshot, updated FROM plans ORDER BY updated DESC').fetchall()
        for payload, updated in row:
            value = json.loads(payload)
            if value.get('volume') == volume:
                value['saved_at'] = updated
                return value
        return None

    def event(self, action, signature, pid, outcome):
        with self.connect() as db:
            cursor = db.execute('INSERT INTO events(action,signature,pid,outcome,created) VALUES (?,?,?,?,?)',
                                (action, signature, pid, outcome, time.time()))
            return cursor.lastrowid

    def finish(self, event_id, outcome):
        with self.connect() as db:
            db.execute('UPDATE events SET outcome=? WHERE id=?', (outcome, event_id))
