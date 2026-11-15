import hashlib
import threading
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
import test_dashboard
import batch_queue
import vault

class BatchTests(unittest.TestCase):
    setUp=test_dashboard.DashboardTests.setUp
    tearDown=test_dashboard.DashboardTests.tearDown
    def test_tracking_urls_and_duplicates(self):
        self.assertEqual(batch_queue.repos('https://huggingface.co/owner/model?utm_source=chatgpt.com\nowner/model\nother/repo'),['owner/model','other/repo'])
        for value in ['','https://evil.example/owner/repo','owner/repo/tree/main','../file']:
            with self.assertRaises(ValueError):batch_queue.repos(value)
    def test_auto_preview_native_and_failed_repo(self):
        controller=Mock();controller.lock=threading.Lock();controller.previews={}
        controller.preview_model.side_effect=[{'plan':{'items':[self.model],'total_bytes':8},'preview':'token'},ValueError('missing')]
        with patch.object(vault,'api',return_value={'siblings':[{'rfilename':'model.safetensors'}]}):
            result=batch_queue.preview(self.root,controller,{'links':'owner/model\nother/missing','format':'auto'})
        self.assertEqual(controller.preview_model.call_args_list[0].args[0]['format'],'native')
        self.assertEqual(result['rows'][1]['status'],'unavailable')
        self.assertEqual(result['total_bytes'],8)
        self.assertTrue((self.root/'batch-previews'/(result['batch']+'.json')).exists())
    def test_enqueue_preserves_main_plan_and_category(self):
        key='a'*32;model={**self.model,'repo':'new/model'}
        vault.atomic(self.root/'batch-previews'/(key+'.json'),{'status':'completed','candidates':[{'status':'validated','plan':{'items':[model]}}]})
        with patch.object(Path,'home',return_value=self.root),patch.object(vault.shutil,'disk_usage',return_value=Mock(free=1000*vault.GIB)):
            result=batch_queue.enqueue(self.root,dict(batch=key,indices=[0],categories={'0':'Abliterated'},signature=hashlib.sha256(self.plan.read_bytes()).hexdigest(),budget_gib=100))
        self.assertEqual(result['added'],1)
        self.assertEqual(vault.read(self.plan)['items'][0],self.model)
        self.assertEqual(vault.read(self.plan)['items'][1]['category'],'Abliterated')
    def test_bad_batch_id_rejected(self):
        with self.assertRaises(ValueError):batch_queue.enqueue(self.root,{'batch':'../escape'})
