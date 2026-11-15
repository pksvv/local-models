"""Structured JSONL output for CLI jobs; no changes to download checkpoints."""
from datetime import datetime, timezone
import json
import os
import sys
import threading
import uuid

JOB_ID = os.environ.get('MODEL_VAULT_JOB_ID') or ('job-' + uuid.uuid4().hex[:12])


def emit(event, message, level='INFO', **fields):
    stream = getattr(sys.stdout, 'original', sys.stdout)
    record = dict(timestamp=datetime.now(timezone.utc).isoformat(), level=level,
                  job_id=JOB_ID, event=event, message=message, **fields)
    stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    stream.flush()


class StructuredOutput:
    def __init__(self, original, level='INFO'):
        self.original = original
        self.level = level
        self.buffer = ''
        self.lock = threading.Lock()

    def write(self, value):
        with self.lock:
            self.buffer += value
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                if line.strip():
                    level = 'ERROR' if any(x in line for x in ('RETRY REQUIRED', 'RuntimeError:', 'Error:')) else self.level
                    emit('output', line, level)
        return len(value)

    def flush(self):
        self.original.flush()

    def isatty(self):
        return False
