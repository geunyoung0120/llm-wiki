import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
try:
    from desktop_jobs import JobManager
except ImportError:
    JobManager = None

class JobTests(unittest.TestCase):
    def test_direct_request_executes_once_without_an_approval_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            jobs=JobManager(folder,None,lambda *args:calls.append(args) or 'saved report')
            reply=jobs.start('save','lesson','claude')
            result=jobs.status(reply['job_id'],wait_seconds=2)
            self.assertEqual(reply['status'],'queued')
            self.assertEqual(result['status'],'done'); self.assertEqual(len(calls),1)
            self.assertNotIn('승인',reply['output'])

    def manager(self, folder, approve, execute):
        self.assertIsNotNone(JobManager, 'bounded desktop jobs are missing')
        return JobManager(Path(folder), approve, execute)

    def test_returns_before_slow_approval_and_recovers_result_without_reexecution(self):
        with tempfile.TemporaryDirectory() as folder:
            gate=threading.Event(); calls=[]
            def approve(*args): gate.wait(2); return True
            def execute(*args): calls.append(args); return 'actual changes and backup'
            jobs=self.manager(folder,approve,execute)
            started=time.monotonic(); reply=jobs.start('save','private synthetic context','claude')
            self.assertLess(time.monotonic()-started,.5)
            self.assertEqual(reply['status'],'awaiting_approval'); self.assertEqual(calls,[])
            gate.set(); result=jobs.status(reply['job_id'],wait_seconds=2)
            self.assertEqual(result['status'],'done'); self.assertEqual(result['output'],'actual changes and backup')
            reader=self.manager(folder,lambda *a:self.fail('prompted'),lambda *a:self.fail('executed'))
            self.assertEqual(reader.status(reply['job_id'])['output'],result['output'])
            self.assertEqual(reader.status()['job_id'],reply['job_id']); self.assertEqual(len(calls),1)
            self.assertNotIn('private synthetic context',''.join(p.read_text() for p in Path(folder).glob('*.json')))

    def test_busy_second_manager_does_not_queue_another_save(self):
        with tempfile.TemporaryDirectory() as folder:
            gate=threading.Event(); calls=[]
            a=self.manager(folder,lambda *args:gate.wait(2),lambda *args:calls.append(args) or 'saved')
            b=self.manager(folder,lambda *args:self.fail('second prompt'),lambda *args:self.fail('second execution'))
            first=a.start('save','one','claude'); second=b.start('save','two','claude')
            self.assertEqual(second['status'],'busy'); self.assertEqual(second['job_id'],first['job_id'])
            gate.set(); self.assertEqual(a.status(first['job_id'],wait_seconds=2)['status'],'done')
            self.assertEqual(len(calls),1)

    def test_cancelled_is_terminal_and_never_executes(self):
        with tempfile.TemporaryDirectory() as folder:
            jobs=self.manager(folder,lambda *a:False,lambda *a:self.fail('executed'))
            reply=jobs.start('save','one','claude')
            self.assertEqual(jobs.status(reply['job_id'],wait_seconds=2)['status'],'cancelled')

    def test_exception_reports_unknown_not_false_no_changes_and_never_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            def execute(*args): calls.append(args); raise RuntimeError('private data')
            jobs=self.manager(folder,lambda *a:True,execute); reply=jobs.start('save','one','claude')
            result=jobs.status(reply['job_id'],wait_seconds=2)
            self.assertEqual(result['status'],'unknown'); self.assertNotIn('private data',str(result))
            self.assertEqual(len(calls),1)

    def test_invalid_status_cannot_escape_and_discovery_does_not_start_work(self):
        with tempfile.TemporaryDirectory() as folder:
            jobs=self.manager(folder,lambda *a:self.fail('prompted'),lambda *a:self.fail('executed'))
            self.assertEqual(jobs.status()['status'],'not_found')
            for invalid in ('../secret','bad','x'*32): self.assertEqual(jobs.status(invalid)['status'],'not_found')
            for context in ('','x'*(2*1024*1024+1)):
                with self.assertRaises(ValueError): jobs.start('save',context,'claude')
            self.assertEqual(list(Path(folder).glob('*.json')),[])

    def test_dead_owner_pending_receipt_is_unknown_and_not_replayed(self):
        with tempfile.TemporaryDirectory() as folder:
            job_id='a'*32
            Path(folder,job_id+'.json').write_text(json.dumps(dict(job_id=job_id,status='running',owner_pid=99999999,created_ns=1,output='running')))
            jobs=self.manager(folder,lambda *a:self.fail('prompted'),lambda *a:self.fail('executed'))
            self.assertEqual(jobs.status(job_id)['status'],'unknown')

    def test_live_owner_without_a_locked_job_is_unknown(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            job_id='b'*32
            Path(folder,job_id+'.json').write_text(json.dumps(dict(job_id=job_id,operation='save',status='running',owner_pid=os.getpid(),created_ns=1,output='running')))
            jobs=self.manager(folder,lambda *a:self.fail('prompted'),lambda *a:self.fail('executed'))
            self.assertEqual(jobs.status(job_id)['status'],'unknown')

    def test_malformed_receipt_cannot_poison_latest_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'c'*32+'.json').write_text('[]')
            jobs=self.manager(folder,lambda *a:self.fail('prompted'),lambda *a:self.fail('executed'))
            self.assertEqual(jobs.status()['status'],'not_found')

    def test_closed_before_approval_does_not_execute(self):
        with tempfile.TemporaryDirectory() as folder:
            gate=threading.Event()
            jobs=self.manager(folder,lambda *a:gate.wait(2),lambda *a:self.fail('executed'))
            reply=jobs.start('save','one','claude'); jobs.close(); gate.set()
            self.assertEqual(jobs.status(reply['job_id'],wait_seconds=2)['status'],'unknown')

    def test_thread_start_failure_leaves_recoverable_unknown(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            jobs=self.manager(folder,lambda *a:self.fail('prompted'),lambda *a:self.fail('executed'))
            with patch('desktop_jobs.threading.Thread.start',side_effect=RuntimeError('start failed')):
                with self.assertRaises(RuntimeError): jobs.start('save','one','claude')
            self.assertEqual(jobs.status()['status'],'unknown')

    def test_malformed_status_and_operation_fields_are_skipped_or_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            job_id='d'*32
            path=Path(folder,job_id+'.json')
            jobs=self.manager(folder,lambda *a:self.fail('prompted'),lambda *a:self.fail('executed'))
            path.write_text(json.dumps(dict(job_id=job_id,status=[],created_ns=1,output='x')))
            self.assertEqual(jobs.status()['status'],'not_found')
            path.write_text(json.dumps(dict(job_id=job_id,operation=[],status='running',created_ns=1,output='x')))
            self.assertEqual(jobs.status(job_id)['status'],'unknown')

    def test_failed_final_receipt_does_not_spin_or_false_success(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            gate=threading.Event()
            jobs=self.manager(folder,lambda *a:True,lambda *a:gate.wait(2) or 'actual output')
            real_write=jobs._write; real_read=jobs._read; reads=[]
            def write(receipt):
                if receipt['status']=='done': raise OSError('synthetic disk error')
                return real_write(receipt)
            def read(job_id): reads.append(job_id); return real_read(job_id)
            with patch.object(jobs,'_write',side_effect=write),patch.object(jobs,'_read',side_effect=read),patch('threading.excepthook'):
                reply=jobs.start('save','one','claude')
                # Ensure the reader holds the worker event before terminal persistence fails.
                timer=threading.Timer(.05,gate.set); timer.start()
                result=jobs.status(reply['job_id'],wait_seconds=.3); timer.join()
                self.assertEqual(result['status'],'unknown')
                self.assertLess(len(reads),20)
