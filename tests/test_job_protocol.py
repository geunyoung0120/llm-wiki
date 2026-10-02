"""Real MCP stdio across a client timeout, using only synthetic local worker output."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from chat_bridge import ROOT, worker_environment

FIXTURE='''import sys,time\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nfrom desktop_jobs import JobManager\nfrom chat_bridge import make_server,desktop_jobs\nroot=Path(sys.argv[2])\ndef execute(operation,text,source):\n    with (root/'calls').open('a') as file: file.write('one call\\n')\n    time.sleep(.4)\n    return 'actual synthetic report and backup'\njobs=desktop_jobs(root/'config.json',execute)\ntry: make_server(None,jobs).run(transport='stdio')\nfinally: jobs.close()\n'''

class ProtocolTests(unittest.TestCase):
    def test_client_timeout_recovers_same_job_and_restart_without_reexecution(self):
        asyncio.run(self.verify())

    async def verify(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); fixture=root/'server.py'; fixture.write_text(FIXTURE)
            params=StdioServerParameters(command=sys.executable,args=[str(fixture),str(ROOT),str(root)],env=worker_environment())
            async with stdio_client(params) as streams:
                async with ClientSession(*streams,read_timeout_seconds=5) as session:
                    await session.initialize()
                    async def call(name,arguments,timeout=5):
                        result=await session.call_tool(name,arguments,read_timeout_seconds=timeout)
                        self.assertFalse(result.is_error)
                        return result.structured_content or json.loads(result.content[0].text)
                    initial=await call('study_save',{'context':'synthetic context','source':'claude'})
                    self.assertEqual(initial['status'],'queued')
                    with self.assertRaises(Exception):
                        await call('study_status',{'job_id':initial['job_id'],'wait_seconds':1},timeout=.1)
                    # The worker can finish despite timeout of a READ-ONLY status call.
                    for attempt in range(30):
                        result=await call('study_status',{'job_id':initial['job_id']})
                        if result['status']=='done':break
                        await asyncio.sleep(.02)
                    self.assertEqual(result['status'],'done')
                    self.assertIn('actual synthetic report',result['output'])
                    self.assertEqual((root/'calls').read_text(),'one call\n')
            async with stdio_client(params) as streams:
                async with ClientSession(*streams,read_timeout_seconds=5) as session:
                    await session.initialize()
                    value=await session.call_tool('study_status',{})
                    recovered=value.structured_content or json.loads(value.content[0].text)
                    self.assertEqual(recovered['job_id'],initial['job_id'])
                    self.assertEqual(recovered['status'],'done')
                    self.assertEqual((root/'calls').read_text(),'one call\n')
            receipts=''.join(p.read_text() for p in (root/'desktop-jobs').rglob('*.json'))
            self.assertNotIn('synthetic context',receipts)
