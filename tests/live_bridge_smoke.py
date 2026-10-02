"""Opt-in real stdio + job recovery + Codex test, synthetic disposable vault only."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

FIXTURE='''import sys\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nfrom chat_bridge import Backend, make_server, job_directory\nfrom desktop_jobs import JobManager\nconfig=Path(sys.argv[2])\nexecute=Backend(config)\njobs=JobManager(job_directory(config), lambda operation,text,source: text != 'CANCEL SYNTHETIC', execute)\ntry: make_server(None,jobs).run(transport='stdio')\nfinally: jobs.close(); execute.close()\n'''

async def verify(work,config,fixture):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from chat_bridge import worker_environment
    from desktop_jobs import JobManager
    params=StdioServerParameters(command=sys.executable,args=[str(fixture),str(ROOT),str(config)],env=worker_environment())
    async with stdio_client(params) as streams:
        async with ClientSession(*streams,read_timeout_seconds=25) as session:
            await session.initialize()
            tools=await session.list_tools()
            assert {t.name for t in tools.tools}=={'study_save','study_load','study_status'}
            async def call(name,arguments):
                value=await session.call_tool(name,arguments)
                assert not value.is_error,value
                return value.structured_content or json.loads(value.content[0].text)
            async def finish(reply):
                deadline=time.monotonic()+650
                while reply['status'] in {'awaiting_approval','running'} and time.monotonic()<deadline:
                    reply=await call('study_status',{'job_id':reply['job_id'],'wait_seconds':20})
                return reply
            reply=await call('study_save',{'context':'CANCEL SYNTHETIC','source':'claude'})
            assert reply['status']=='awaiting_approval'
            assert (await finish(reply))['status']=='cancelled'
            assert not list((work/'vault').rglob('*.md'))
            print('PASS: real stdio cancellation does not launch Codex or write notes.',flush=True)
            packet='Synthetic lesson: A cache retains computed results to avoid repeated work. Learner thought caching always improves correctness. Correction: cached values may become stale and invalidation is necessary. Open question: how should TTL be chosen?'
            start=time.monotonic()
            reply=await call('study_save',{'context':packet,'source':'claude'})
            assert time.monotonic()-start<2, 'acknowledgment blocked on Codex'
            assert reply['status']=='awaiting_approval'
            result=await finish(reply)
            assert result['status']=='done',result
            notes={p.relative_to(work/'vault'):p.read_bytes() for p in (work/'vault').rglob('*.md')}
            assert notes and 'Applied changes:' in result['output'],result
            again=await call('study_status',{'job_id':reply['job_id']})
            assert again['output']==result['output']
            assert notes=={p.relative_to(work/'vault'):p.read_bytes() for p in (work/'vault').rglob('*.md')}
            print('PASS: immediate job id, actual Codex notes, recoverable actual report without another save.',flush=True)
            reply=await call('study_load',{'topic':'cache staleness and TTL','source':'claude'})
            result=await finish(reply)
            assert result['status']=='done' and result['output'].strip(),result
            assert notes=={p.relative_to(work/'vault'):p.read_bytes() for p in (work/'vault').rglob('*.md')}
            print('PASS: actual Codex retrieval with vault bytes unchanged.',flush=True)
    # New MCP process must recover saved receipts without approval/backend execution.
    async with stdio_client(params) as streams:
        async with ClientSession(*streams,read_timeout_seconds=25) as session:
            await session.initialize()
            receipt=await session.call_tool('study_status',{})
            assert (receipt.structured_content or json.loads(receipt.content[0].text))['status']=='done',receipt
            assert notes=={p.relative_to(work/'vault'):p.read_bytes() for p in (work/'vault').rglob('*.md')}
            print('PASS: connection restart recovered completion; no raw session persisted.',flush=True)
    for path in work.rglob('*.json'):
        assert packet not in path.read_text(), 'raw context persisted'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',action='store_true')
    if not parser.parse_args().run:parser.error('Use --run to deliberately test actual Codex in a synthetic vault.')
    with tempfile.TemporaryDirectory(prefix='study-local-live-') as folder:
        work=Path(folder); (work/'vault').mkdir()
        config=json.loads((Path.home()/'.config/study-save/config.json').read_text())
        config.update(vault=str(work/'vault'),state_dir=str(work/'state'),language='Korean',cleanup=False)
        path=work/'config.json';path.write_text(json.dumps(config))
        fixture=work/'server.py';fixture.write_text(FIXTURE)
        asyncio.run(verify(work,path,fixture))

if __name__=='__main__':main()
