import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_dashboard
import research
import vault

class ResearchTests(unittest.TestCase):
    setUp=test_dashboard.DashboardTests.setUp
    tearDown=test_dashboard.DashboardTests.tearDown
    def fixture(self):
        worker=research.Research(self.root,None)
        model={**self.model,'repo':'other/new'}
        vault.atomic(worker.path,dict(status='completed',candidates=[dict(status='validated',plan={'items':[model]})]))
        return worker
    def test_append_preserves_old_queue_and_never_launches(self):
        worker=self.fixture();signature=hashlib.sha256(self.plan.read_bytes()).hexdigest()
        with patch.object(Path,'home',return_value=self.root),patch.object(research.subprocess,'Popen') as spawn,patch.object(vault.shutil,'disk_usage',return_value=type('Usage',(),{'free':1000*vault.GIB})()):
            result=worker.enqueue([0],signature,1)
            spawn.assert_not_called()
        self.assertEqual(result['added'],1)
        plan=json.loads(self.plan.read_text())
        self.assertEqual(plan['items'][0],self.model)
        self.assertEqual(len(plan['items']),2)
        self.assertTrue(list((self.root/'queue-history').glob('*.json')))
    def test_stale_queue_and_budget_rejected(self):
        worker=self.fixture();before=self.plan.read_bytes()
        with patch.object(Path,'home',return_value=self.root):
            with self.assertRaisesRegex(ValueError,'changed'):worker.enqueue([0],'bad',1)
            data=vault.read(worker.path);data['candidates'][0]['plan']['items'][0]['files']=[{'name':'large.gguf','size':2*vault.GIB}];vault.atomic(worker.path,data)
            with self.assertRaisesRegex(ValueError,'budget'):worker.enqueue([0],hashlib.sha256(before).hexdigest(),1)
        self.assertEqual(before,self.plan.read_bytes())
    def test_invalid_selection_and_unvalidated_rejected(self):
        worker=self.fixture()
        with self.assertRaises(ValueError):worker.enqueue([-1],'',100)
        data=vault.read(worker.path);data['candidates'][0]['status']='unavailable';vault.atomic(worker.path,data)
        with self.assertRaisesRegex(ValueError,'validated'):worker.enqueue([0],'',100)
    def test_background_agent_installed_blocks_queue_update(self):
        worker=self.fixture();agent=self.root/'Library/LaunchAgents/com.vipul.model-vault.plist';agent.parent.mkdir(parents=True);agent.write_text('test')
        with patch.object(Path,'home',return_value=self.root):
            with self.assertRaisesRegex(ValueError,'login agent'):worker.enqueue([0],'',100)

    def test_phrase_validation(self):
        self.assertEqual(research.Research.query('  abliterated Qwen coding  '),'abliterated Qwen coding')
        self.assertEqual(research.Research.query(''),'')
        for value in [None,[], 'x'*301, 'bad\nquery']:
            with self.assertRaises(ValueError):research.Research.query(value)

    def test_research_activity_reports_real_search_events(self):
        worker=research.Research(self.root,None);worker.running=True
        vault.atomic(worker.path,dict(status='running',query='image',started=1,log_offset=0))
        (self.root/'research-agent.log').write_text('bad line\n'+json.dumps({'item':{'type':'web_search','query':'image model releases'}})+'\n')
        state=worker.state()
        self.assertEqual(state['activity'],['image model releases'])
        self.assertEqual(state['recent_search_events'],1)
