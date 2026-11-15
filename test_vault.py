import hashlib, http.server, json, multiprocessing, os, tempfile, threading, unittest
from pathlib import Path
import vault
DATA=b'0123456789abcdef'*(1024*512)
class Handler(http.server.BaseHTTPRequestHandler):
    starts=[]; ignore=False; bad=False
    def log_message(self,*a):pass
    def do_GET(self):
        start=int(self.headers.get('Range','bytes=0-').split('=')[1].split('-')[0])
        Handler.starts.append(start)
        if Handler.ignore:start=0
        self.send_response(206 if start else 200)
        if start:self.send_header('Content-Range',f'bytes {start+1 if Handler.bad else start}-{len(DATA)-1}/{len(DATA)}')
        self.send_header('Content-Length',str(len(DATA)-start));self.end_headers()
        try:self.wfile.write(DATA[start:])
        except (BrokenPipeError,ConnectionResetError):pass

def crash(url,dest,item):
    vault.CHECKPOINT_BYTES=1024**2
    def check():
        cp=Path(str(dest)+'.checkpoint.json')
        if cp.exists() and json.loads(cp.read_text())['offset']>=2*1024**2:os._exit(99)
    vault.download(url,dest,item,check=check,reserve=0)

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}/file'
        cls.item=dict(name='file',size=len(DATA),sha256=hashlib.sha256(DATA).hexdigest())
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dest=Path(self.tmp.name)/'file';Handler.starts=[];Handler.ignore=False;Handler.bad=False
    def tearDown(self):self.tmp.cleanup()
    def partial(self):
        offset=1024**2
        Path(str(self.dest)+'.part').write_bytes(DATA[:offset]+b'uncheckpointed bytes')
        vault.atomic(str(self.dest)+'.checkpoint.json',dict(offset=offset,fingerprint=[self.url,len(DATA),self.item['sha256'],None]))
    def test_hard_process_kill_then_resume(self):
        p=multiprocessing.get_context('fork').Process(target=crash,args=(self.url,self.dest,self.item));p.start();p.join(10)
        self.assertEqual(p.exitcode,99)
        cp=json.loads(Path(str(self.dest)+'.checkpoint.json').read_text());self.assertGreater(cp['offset'],0)
        vault.download(self.url,self.dest,self.item,reserve=0)
        self.assertIn(cp['offset'],Handler.starts);self.assertTrue(vault.valid(self.dest,self.item))
    def test_uncommitted_tail_truncated(self):
        self.partial();vault.download(self.url,self.dest,self.item,reserve=0);self.assertTrue(vault.valid(self.dest,self.item));self.assertEqual(Handler.starts,[1024**2])
    def test_fully_checkpointed_partial_reused_without_network(self):
        Path(str(self.dest)+'.part').write_bytes(DATA)
        vault.atomic(str(self.dest)+'.checkpoint.json',dict(offset=len(DATA),fingerprint=[self.url,len(DATA),self.item['sha256'],None]))
        self.assertEqual(vault.download(self.url,self.dest,self.item,reserve=0),'verified partial')
        self.assertTrue(vault.valid(self.dest,self.item));self.assertEqual(Handler.starts,[])
        self.assertFalse(Path(str(self.dest)+'.checkpoint.json').exists())
    def test_server_ignores_range(self):
        self.partial();Handler.ignore=True;vault.download(self.url,self.dest,self.item,reserve=0);self.assertTrue(vault.valid(self.dest,self.item))
    def test_bad_range_rejected(self):
        self.partial();Handler.bad=True
        with self.assertRaisesRegex(RuntimeError,'range'):vault.download(self.url,self.dest,self.item,reserve=0)
    def test_completed_corruption_repaired(self):
        self.dest.write_bytes(b'x'*len(DATA));vault.download(self.url,self.dest,self.item,reserve=0);self.assertTrue(vault.valid(self.dest,self.item))
    def test_reserve_stops_download(self):
        with self.assertRaisesRegex(RuntimeError,'reserve'):vault.download(self.url,self.dest,self.item,reserve=10**18)
        self.assertEqual(Handler.starts,[])
    def test_missing_drive_stops_before_writes(self):
        def guard():raise RuntimeError('drive missing')
        with self.assertRaises(RuntimeError):vault.download(self.url,self.dest,self.item,check=guard,reserve=0)
        self.assertFalse(self.dest.exists());self.assertEqual(list(Path(self.tmp.name).iterdir()),[])
    def test_shards_selected(self):
        files=[dict(rfilename=n,size=1,blobId='x') for n in ['a-Q4_K_M-00001-of-00002.gguf','a-Q4_K_M-00002-of-00002.gguf','a-Q8_0.gguf','README.md','mmproj-f16.gguf','mmproj-f32.gguf']]
        chosen=vault.select(dict(format='gguf',quant='Q4_K_M'),files)
        self.assertEqual(len(chosen),4)
    def test_single_file_preferred_to_duplicate_shards(self):
        chosen=vault.select(dict(format='gguf',quant='Q4_K_M'),[dict(rfilename=n,size=1,blobId='x') for n in ['a-Q4_K_M.gguf','a-Q4_K_M-00001-of-00002.gguf','a-Q4_K_M-00002-of-00002.gguf']])
        self.assertEqual(len(chosen),1)
    def test_native_excludes_duplicate_bins(self):
        chosen=vault.select(dict(format='native'),[dict(rfilename=n,size=1,blobId='x') for n in ['model.safetensors','pytorch_model.bin','config.json','tokenizer.json','README.md']]);self.assertEqual(len(chosen),4)
    def test_path_traversal(self):
        with self.assertRaises(ValueError):vault.safe('../oops')
if __name__=='__main__':unittest.main()
