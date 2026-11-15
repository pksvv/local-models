import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import job_log
import jobs


class JobTests(unittest.TestCase):
    def test_structured_lines_include_identity_time_level(self):
        output=io.StringIO()
        with patch.object(job_log.sys,'stdout',output):
            wrapper=job_log.StructuredOutput(output)
            wrapper.write('First ');wrapper.write('line\nRuntimeError: failed\n')
        lines=[json.loads(s) for s in output.getvalue().splitlines()]
        self.assertEqual(lines[0]['message'],'First line')
        self.assertEqual(lines[1]['level'],'ERROR')
        self.assertTrue(lines[0]['job_id']);self.assertIn('timestamp',lines[0])

    def test_job_metadata_and_logs_survive_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata,log=jobs.create(tmp,'specific: owner/model','signature')
            jobs.update(tmp,metadata,status='completed',ended=metadata['started']+10,exit_code=0)
            log.write_text(json.dumps(dict(timestamp='2026-01-01T00:00:00Z',event='file_started',file='new.gguf',level='INFO',message='checking'))+'\n')
            found=jobs.history(tmp)[0]
            self.assertEqual(found['id'],metadata['id'])
            self.assertEqual(found['name'],'Download owner/model')
            self.assertEqual(found['status'],'completed')
            self.assertEqual(found['elapsed_seconds'],10)
            self.assertEqual(found['current_file'],'new.gguf')

    def test_truncated_log_and_dead_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata,log=jobs.create(tmp,'start','signature')
            jobs.update(tmp,metadata,status='running',pid=999999999)
            log.write_text('broken line\n'+json.dumps(dict(timestamp='time',event='progress',file='old.gguf',level='INFO',message='checkpoint'))+'\n'+json.dumps(dict(timestamp='later',event='file_started',file='new.gguf',level='INFO',message='checking'))+'\n{"partial":')
            found=jobs.history(tmp)[0]
            self.assertEqual(found['status'],'interrupted')
            self.assertEqual(len(found['logs']),2)
            self.assertIsNone(found['progress'])

    def test_finish_record_overrides_running_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata,log=jobs.create(tmp,'verify','signature')
            log.write_text(json.dumps(dict(timestamp='time',event='job_finished',status='failed',level='ERROR',message='failure'))+'\n')
            self.assertEqual(jobs.history(tmp)[0]['status'],'failed')

    def test_real_subprocess_lifecycle_is_recorded_without_downloads(self):
        import dashboard
        import sys
        import time
        from queue_store import QueueStore
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            controller=dashboard.Controller(QueueStore(root/'index.sqlite3'))
            with patch.object(dashboard,'APP',root):
                controller._launch([sys.executable,'-c',"import json,os; print(json.dumps(dict(timestamp='2026-01-01T00:00:00Z',job_id=os.environ['MODEL_VAULT_JOB_ID'],event='output',level='INFO',message='local test only')))"], 'verify', 'signature')
                controller.process.wait(timeout=5)
                for _ in range(100):
                    found=jobs.history(root)[0]
                    if found.get('exit_code')==0:break
                    time.sleep(.01)
                self.assertEqual(found['status'],'completed')
                self.assertEqual(found['logs'][0]['job_id'],found['id'])
                self.assertEqual(found['exit_code'],0)

if __name__=='__main__':unittest.main()
