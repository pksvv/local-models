import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import vault
import library

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.volume=Path(self.tmp.name);self.root=self.volume/'ModelVault';self.root.mkdir()
        self.cfg={'volume':str(self.volume)}
        self.model=dict(repo='owner/model',revision='commit',category='General',files=[dict(name='model.gguf',size=4)])
        self.dest=self.root/'models/owner/model/commit/model.gguf';self.dest.parent.mkdir(parents=True)
        self.guard=patch.object(vault,'guard');self.guard.start()
    def tearDown(self):self.guard.stop();self.tmp.cleanup()
    def test_complete_inventory_deduplicates_main_and_specific(self):
        self.dest.write_bytes(b'data')
        vault.atomic(self.root/'status.json',{str(self.dest.relative_to(self.root)):{'status':'downloaded + verified','time':123}})
        result=library.inventory(self.cfg,[{'items':[self.model]},{'items':[self.model]}])
        self.assertTrue(result['available']);self.assertEqual(len(result['models']),1)
        self.assertEqual(result['models'][0]['verification'],'Previously verified')
        self.assertEqual(result['models'][0]['location'],str(self.dest.parent))
    def test_missing_partial_or_wrong_size_not_downloaded(self):
        for data in [b'',b'bad']:
            self.dest.write_bytes(data)
            self.assertEqual(library.inventory(self.cfg,[{'items':[self.model]}])['models'],[])
        self.dest.unlink();self.dest.with_suffix('.part').write_bytes(b'data')
        self.assertEqual(library.inventory(self.cfg,[{'items':[self.model]}])['models'],[])
    def test_existing_size_does_not_invent_verification(self):
        self.dest.write_bytes(b'data')
        self.assertEqual(library.inventory(self.cfg,[{'items':[self.model]}])['models'][0]['verification'],'Verification pending')
    def test_offline_and_unsafe_paths(self):
        self.assertFalse(library.inventory(self.cfg,[],cached=True)['available'])
        self.model['files'][0]['name']='../escape'
        self.assertFalse(library.inventory(self.cfg,[{'items':[self.model]}])['available'])

if __name__=='__main__':unittest.main()
