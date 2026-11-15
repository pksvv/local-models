import tempfile
from pathlib import Path
import unittest
import matching

class MatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.model=dict(repo='Qwen/Qwen3-8B-GGUF',revision='abc',files=[dict(name='Q4_K_M.gguf',size=4)],_queued=True)
    def tearDown(self):self.tmp.cleanup()
    def test_exact_queued_and_downloaded(self):
        self.assertEqual(matching.hints(self.model,[self.model],self.root)[0]['kind'],'already_queued')
        p=self.root/'models/Qwen/Qwen3-8B-GGUF/abc/Q4_K_M.gguf';p.parent.mkdir(parents=True);p.write_bytes(b'data')
        self.assertEqual(matching.hints(self.model,[self.model],self.root)[0]['kind'],'already_downloaded')
    def test_other_publisher_and_tuning_flagged_not_equal(self):
        candidate={**self.model,'repo':'bartowski/Qwen3-8B-abliterated-GGUF'}
        result=matching.hints(candidate,[self.model],self.root)[0]
        self.assertEqual(result['kind'],'possible_match');self.assertIn('parameter size',result['reason'])
    def test_different_size_has_explicit_reason(self):
        candidate={**self.model,'repo':'other/Qwen3-14B-GGUF'}
        self.assertIn('different parameter size',matching.hints(candidate,[self.model],self.root)[0]['reason'])
    def test_same_repo_new_revision_or_quant(self):
        candidate={**self.model,'revision':'new'}
        self.assertEqual(matching.hints(candidate,[self.model],self.root)[0]['kind'],'possible_match')
        candidate={**self.model,'files':[dict(name='Q8.gguf',size=8)]}
        self.assertEqual(matching.hints(candidate,[self.model],self.root)[0]['kind'],'possible_match')
    def test_unrelated_and_missing_historical_entries_not_flagged(self):
        self.assertEqual(matching.hints({**self.model,'repo':'other/Whisper-large'},[self.model],self.root),[])
        self.assertEqual(matching.hints(self.model,[{**self.model,'_queued':False}],self.root),[])
