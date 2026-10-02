"""Direct manual transport with no extra native dialog or implicit work."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import chat_bridge as bridge


class LocalBridgeTests(unittest.TestCase):
    def jobs(self, execute):
        folder=tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        return bridge.desktop_jobs(Path(folder.name)/'config.json',execute)

    def test_direct_save_executes_once_without_native_dialog(self):
        calls=[]; jobs=self.jobs(lambda *a:calls.append(a) or 'actual report')
        with patch('chat_bridge.subprocess.Popen',side_effect=AssertionError('native dialog attempted')):
            reply=jobs.start('save','lesson','claude')
            result=jobs.status(reply['job_id'],wait_seconds=2)
        self.assertEqual(reply['status'],'queued')
        self.assertEqual(result['status'],'done'); self.assertEqual(result['output'],'actual report')
        self.assertEqual(calls,[('save','lesson','claude')])
        self.assertEqual(jobs.status(reply['job_id'])['output'],'actual report')
        self.assertEqual(len(calls),1)

    def test_direct_load_requires_no_native_dialog(self):
        calls=[]; jobs=self.jobs(lambda *a:calls.append(a) or 'retrieved packet')
        reply=jobs.start('load','cache','claude')
        self.assertEqual(jobs.status(reply['job_id'],wait_seconds=2)['output'],'retrieved packet')
        self.assertEqual(calls,[('load','cache','claude')])

    def test_invalid_context_does_not_start_work(self):
        jobs=self.jobs(lambda *a:self.fail('executed'))
        for context in ('', 'x'*(2*1024*1024+1)):
            with self.assertRaises(ValueError):jobs.start('save',context,'claude')
        self.assertEqual(jobs.status()['status'],'not_found')

    def test_backend_failure_is_unknown_and_not_retried(self):
        calls=[]
        def execute(*a):calls.append(a); raise RuntimeError('sensitive packet')
        jobs=self.jobs(execute); reply=jobs.start('save','lesson','claude')
        result=jobs.status(reply['job_id'],wait_seconds=2)
        self.assertEqual(result['status'],'unknown'); self.assertEqual(len(calls),1)
        self.assertNotIn('sensitive',str(result))

    def test_mac_venv_launcher_not_in_codex_environment(self):
        with patch.dict(os.environ,{'__PYVENV_LAUNCHER__':'/한글/.venv/python','PYTHONEXECUTABLE':'/한글/.venv/python','_':'/broken/\udcb4/python'}):
            env=bridge.worker_environment()
        self.assertTrue('__PYVENV_LAUNCHER__' not in env)
        self.assertTrue('PYTHONEXECUTABLE' not in env)
        self.assertTrue('_' not in env)

    def test_discovery_does_not_execute(self):
        jobs=self.jobs(lambda *a:self.fail('executed'))
        server=bridge.make_server(None,jobs=jobs)
        tools=asyncio.run(server.list_tools())
        self.assertEqual({t.name for t in tools},{'study_save','study_load','study_status'})
        self.assertEqual(jobs.status()['status'],'not_found')

    def test_closed_bridge_does_not_start_more_work(self):
        jobs=self.jobs(lambda *a:self.fail('executed')); jobs.close()
        with self.assertRaises(RuntimeError):jobs.start('save','lesson','claude')

    def test_shutdown_stops_backend_child_and_blocks_later_execution(self):
        worker=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        backend=bridge.Backend(Path('/unused/config.json')); backend.processes.add(worker)
        try:
            backend.close(); self.assertIsNotNone(worker.poll())
            with self.assertRaises(RuntimeError):backend('save','lesson','claude')
        finally:
            if worker.poll() is None:worker.kill(); worker.wait()


if __name__=='__main__':unittest.main()
