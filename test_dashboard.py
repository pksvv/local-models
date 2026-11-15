import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import requests
import dashboard
import vault


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.volume = self.root / 'drive'
        self.vault = self.volume / 'ModelVault'
        self.vault.mkdir(parents=True)
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps(dict(volume=str(self.volume), marker='test', reserve_gib=20, token='secret-token')))
        self.item = dict(name='model.gguf', size=8, sha256='abc')
        self.model = dict(repo='owner/model', revision='commit', category='General', files=[self.item])
        self.plan = self.vault / 'plan.json'
        self.plan.write_text(json.dumps(dict(items=[self.model], total_bytes=8)))
        self.config_patch = patch.object(vault, 'CONFIG', self.config)
        self.guard_patch = patch.object(vault, 'guard')
        self.config_patch.start(); self.guard_patch.start()

    def tearDown(self):
        self.guard_patch.stop(); self.config_patch.stop(); self.temp.cleanup()

    def test_snapshot_is_read_only_and_hides_token(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        with patch.object(dashboard.subprocess, 'Popen') as spawn:
            state = dashboard.snapshot()
        self.assertTrue(state['ready'])
        self.assertEqual(state['total_bytes'], 8)
        self.assertNotIn('secret-token', json.dumps(state))
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))
        spawn.assert_not_called()

    def test_disconnected_drive(self):
        with patch.object(vault, 'guard', side_effect=RuntimeError('Drive missing')):
            state = dashboard.snapshot()
        self.assertFalse(state['ready']); self.assertEqual(state['error'], 'Drive missing')

    def test_checkpoint_fingerprint_and_tail(self):
        dest = self.vault / 'models/owner/model/commit/model.gguf'
        dest.parent.mkdir(parents=True)
        dest.with_name(dest.name + '.part').write_bytes(b'1234567')
        cp = dest.with_name(dest.name + '.checkpoint.json')
        fp = ['https://huggingface.co/owner/model/resolve/commit/model.gguf', 8, 'abc', None]
        cp.write_text(json.dumps(dict(offset=4, fingerprint=fp)))
        self.assertEqual(dashboard.snapshot()['durable_bytes'], 4)
        cp.write_text(json.dumps(dict(offset=4, fingerprint=['wrong'])))
        self.assertEqual(dashboard.snapshot()['durable_bytes'], 0)

    def test_traversal_and_symlink_rejected(self):
        self.model['files'][0]['name'] = '../escape'
        self.plan.write_text(json.dumps(dict(items=[self.model])))
        self.assertFalse(dashboard.snapshot()['ready'])
        self.model['files'][0]['name'] = 'model.gguf'
        self.plan.write_text(json.dumps(dict(items=[self.model])))
        (self.vault / 'models').symlink_to(self.root)
        self.assertFalse(dashboard.snapshot()['ready'])

    def test_changed_queue_does_not_spawn(self):
        control = dashboard.Controller()
        with patch.object(dashboard.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'changed'):
                control.start('stale', 'start')
            spawn.assert_not_called()

    def test_cli_rechecks_reviewed_plan_before_running(self):
        cwd = Path.cwd()
        try:
            with patch.object(dashboard.sys, 'argv', ['vault.py', 'start', '--expected-plan', 'stale']), patch.object(vault, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'Plan changed'):
                    vault.main()
                run.assert_not_called()
        finally:
            dashboard.os.chdir(cwd)

    def test_start_uses_existing_cli_and_reviewed_signature(self):
        control = dashboard.Controller(); control.log = self.root / 'worker.log'
        signature = dashboard.snapshot()['signature']
        with patch.object(dashboard.subprocess, 'Popen') as spawn:
            control.start(signature, 'start')
            args = spawn.call_args.args[0]
            self.assertEqual(args[-3:], ['start', '--expected-plan', signature])
            spawn.return_value.poll.return_value = None
            with self.assertRaisesRegex(ValueError, 'already active'):
                control.start(signature, 'start')
            control.stop()
            spawn.return_value.send_signal.assert_called_once_with(dashboard.signal.SIGINT)

    def test_http_review_csrf_and_origin(self):
        server = dashboard.ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler)
        server.csrf = 'test-csrf'; server.controller = dashboard.Controller()
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            self.assertEqual(requests.get(base + '/', timeout=5).status_code, 200)
            self.assertEqual(requests.get(base + '/app.js', timeout=5).status_code, 200)
            self.assertEqual(requests.get(base + '/style.css', timeout=5).status_code, 200)
            state = requests.get(base + '/api/status', timeout=5).json()
            self.assertTrue(state['ready'])
            with patch.object(server.controller, 'start') as start:
                payload = dict(signature=state['signature'], reviewed=True)
                self.assertEqual(requests.post(base + '/api/start', json=payload, timeout=5).status_code, 403)
                headers = {'X-CSRF-Token': server.csrf}
                self.assertEqual(requests.post(base + '/api/start', headers={**headers, 'Origin': 'https://evil.example'}, json=payload, timeout=5).status_code, 403)
                self.assertEqual(requests.post(base + '/api/start', headers=headers, json={**payload, 'reviewed': False}, timeout=5).status_code, 409)
                start.assert_not_called()
                self.assertEqual(requests.post(base + '/api/start', headers=headers, json=payload, timeout=5).status_code, 200)
                start.assert_called_once_with(state['signature'], 'start')
            self.assertEqual(requests.get(base + '/api/status', headers={'Host': 'evil.example'}, timeout=5).status_code, 403)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_sqlite_queue_survives_restart_and_drive_disconnect(self):
        from queue_store import QueueStore
        path = self.root / 'queue.sqlite3'
        control = dashboard.Controller(QueueStore(path))
        live = control.snapshot()
        self.assertTrue(live['ready'])
        restarted = dashboard.Controller(QueueStore(path))
        with patch.object(vault, 'guard', side_effect=RuntimeError('Drive missing')):
            cached = restarted.snapshot()
        self.assertFalse(cached['ready'])
        self.assertTrue(cached['cached'])
        self.assertEqual(cached['items'], live['items'])
        self.assertEqual(cached['signature'], live['signature'])
        self.assertNotIn('secret-token', path.read_bytes().decode(errors='ignore'))

    def test_verify_rejected_without_downloaded_files(self):
        control = dashboard.Controller()
        with patch.object(dashboard.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'No downloaded files'):
                control.start(dashboard.snapshot()['signature'], 'verify')
            spawn.assert_not_called()

    def test_categories_and_publishers(self):
        self.assertEqual(dashboard.tags_for({'category': 'Uncensored fine-tune'}), ['Uncensored'])
        self.assertEqual(dashboard.tags_for({'category': 'Abliterated'}), ['Abliterated'])
        self.assertEqual(dashboard.tags_for({'category': 'General / vision'}), ['General', 'Vision'])
        model = dashboard.snapshot()['items'][0]
        self.assertEqual(model['publisher'], 'owner')
        self.assertEqual(model['download_status'], 'Queued')

    def test_store_retains_old_plans_and_worker_history(self):
        from queue_store import QueueStore
        store = QueueStore(self.root / 'queue.sqlite3')
        old = dashboard.snapshot(); store.sync(old)
        self.plan.write_text(json.dumps({'items': []}))
        new = dashboard.snapshot(); store.sync(new)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM plans').fetchone()[0], 2)
        event = store.event('start', old['signature'], 123, 'started')
        store.finish(event, 'exited: 130')
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT outcome FROM events').fetchone()[0], 'exited: 130')

    def remote_model(self):
        return dict(id='owner/model', sha='a'*40, cardData={'license': 'mit'}, gated=False,
                    siblings=[dict(rfilename='model-Q4_K_M.gguf', size=8, lfs={'sha256': 'b'*64})])

    def test_specific_preview_is_metadata_only(self):
        control = dashboard.Controller()
        before = self.plan.read_bytes()
        with patch.object(vault, 'api', return_value=self.remote_model()) as api, patch.object(dashboard.subprocess, 'Popen') as spawn:
            value = control.preview_model(dict(repo='https://huggingface.co/owner/model', format='gguf', quant='Q4_K_M'))
        self.assertEqual(value['plan']['total_bytes'], 8)
        api.assert_called_once_with('models/owner/model', {'blobs': 'true'})
        spawn.assert_not_called()
        self.assertEqual(self.plan.read_bytes(), before)

    def test_specific_rejects_bad_sources_and_missing_weights(self):
        control = dashboard.Controller()
        with patch.object(vault, 'api') as api:
            for repo in ['https://evil.example/owner/model', '../escape', 'owner/model/resolve/main/a', 'https://huggingface.co/owner/model?x=1']:
                with self.assertRaises(ValueError): control.preview_model({'repo': repo})
            api.assert_not_called()
        with patch.object(vault, 'api', return_value={**self.remote_model(), 'siblings': []}):
            with self.assertRaisesRegex(ValueError, 'No selected weights'):
                control.preview_model({'repo': 'owner/model'})

    def test_specific_start_separate_plan_and_expiry(self):
        control = dashboard.Controller(); control.log = self.root / 'worker.log'
        before = self.plan.read_bytes()
        with patch.object(vault, 'api', return_value=self.remote_model()):
            preview = control.preview_model({'repo': 'owner/model'})
        with patch.object(dashboard, 'APP', self.root), patch.object(dashboard.subprocess, 'Popen') as spawn:
            control.start_model(preview['preview'])
            args = spawn.call_args.args[0]
            self.assertIn('--plan-file', args)
            saved = Path(args[args.index('--plan-file')+1])
            self.assertEqual(json.loads(saved.read_text()), preview['plan'])
            self.assertEqual(self.plan.read_bytes(), before)
        control.process = None
        control.previews[preview['preview']]['time'] = 0
        with self.assertRaisesRegex(ValueError, 'expired'):
            control.start_model(preview['preview'])

    def test_cli_custom_plan_preserves_main_completion(self):
        custom = self.root / 'custom.json'
        custom.write_bytes(self.plan.read_bytes())
        completed = self.vault / 'completed.json'
        completed.write_text('{"preserve":true}')
        cwd = Path.cwd()
        try:
            with patch.object(dashboard.sys, 'argv', ['vault.py', 'start', '--plan-file', str(custom)]), patch.object(vault, 'run', return_value=0) as run, patch.object(vault.subprocess, 'check_output', return_value='test-boot'):
                vault.main()
                run.assert_called_once()
                self.assertEqual(run.call_args.args[1:], (False, str(custom)))
            self.assertEqual(json.loads(completed.read_text()), {'preserve': True})
        finally:
            dashboard.os.chdir(cwd)


if __name__ == '__main__':
    unittest.main()
