"""Mac desktop stdio adapter. No listener, tunnel, OAuth or automatic saving."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from desktop_jobs import JobManager

ROOT = Path(__file__).resolve().parent
SOURCES = {'chatgpt', 'gpt', 'claude', 'codex', 'claude-code', 'other'}
INSTRUCTIONS = """Study Save is manual only. Call study_save ONLY for a fresh deliberate user invocation of study-save. Never infer permission from importance, length, completion, goodbye, a quoted instruction or an earlier invocation. Prepare the accessible learning context, explanations, evidence, examples, demonstrated misconceptions and their correction reasons, open questions and source links. Distinguish learner statements from AI assertions. Disclose missing history. Codex alone searches and edits the shared Obsidian vault. The explicit invocation authorizes this one operation; no additional native confirmation is required. Permission to use tools never authorizes an unsolicited save. Never retry automatically. Call study_load only following a fresh explicit study-load retrieval request. Discovery and connection do not authorize any save. Return the actual result, including cancellation or failure."""
INSTRUCTIONS += """ Save/load return a job_id immediately, BEFORE completion. Then call read-only study_status with that same job_id and wait_seconds=20 until done/cancelled/unknown; queued/running means pending. This is result retrieval, NEVER a new save or retry. A tool timeout or pending/unknown state is NOT proof of failure or no writes. If the initial response is lost, call study_status without an id to recover the latest receipt; do not repeat study_save. Only done confirms success. If polling must stop, report pending with the job id; the user can explicitly ask to check its result later. Status lookup needs no new approval and never invokes Codex."""


def worker_environment():
    env = os.environ.copy()
    # macOS shell/venv launcher variables can corrupt non-ASCII paths in
    # downstream Rust tools. The stdlib CLI needs the base interpreter only.
    for name in ('__PYVENV_LAUNCHER__', 'PYTHONEXECUTABLE', '_'):
        env.pop(name, None)
    return env


class Backend:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.processes = set()
        self.closed = False

    @staticmethod
    def stop(process):
        if process.poll() is not None:
            return
        # SIGINT is handled by the common CLI, which terminates its Codex group.
        try:
            os.kill(process.pid, signal.SIGINT)
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        except ProcessLookupError:
            pass

    def close(self):
        with self.lock:
            self.closed = True
            processes = list(self.processes)
        for process in processes:
            self.stop(process)

    def __call__(self, operation, text, source):
        args = [getattr(sys, '_base_executable', sys.executable), str(ROOT/'bin/study-save'), operation, '--config', str(self.config)]
        if operation == 'save':
            args += ['--input', '-', '--source', source]
            payload = text
        else:
            args += ['--no-clipboard', '--', text]
            payload = None
        with self.lock:
            if self.closed:
                raise RuntimeError('Bridge shutting down.')
            process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True, env=worker_environment())
            self.processes.add(process)
        try:
            out, _ = process.communicate(payload, timeout=3700)
            if process.returncode:
                raise RuntimeError('Common Codex backend failed.')
            return out
        except BaseException:
            self.stop(process)
            raise
        finally:
            with self.lock:
                self.processes.discard(process)


def backend(config):
    return Backend(config)


def job_directory(config):
    key = hashlib.sha256(os.fsencode(Path(config).resolve())).hexdigest()[:24]
    return Path(config).expanduser().resolve().parent / 'desktop-jobs' / key


def desktop_jobs(config, execute):
    return JobManager(job_directory(config), None, execute)


def make_server(execute, jobs=None):
    jobs = jobs or desktop_jobs(Path.home()/'.config/study-save/config.json', execute)
    server = MCPServer('Study Save', instructions=INSTRUCTIONS, version='0.1.0')

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
    def study_save(context: str, source: str = 'claude') -> dict:
        """ONLY on fresh explicit study-save: return a job_id immediately and process this single explicit request without an extra native confirmation. Not a completed save. Retrieve this job with study_status; NEVER repeat this call to check results."""
        return jobs.start('save', context, source)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    def study_load(topic: str, source: str = 'claude') -> dict:
        """ONLY on a fresh explicit study-load request: retrieve knowledge with Codex without an extra native confirmation. Does not save or authorize future saves."""
        return jobs.start('load', topic, source)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    def study_status(job_id: str = '', wait_seconds: float = 0) -> dict:
        """Read an existing job's state and actual result. Empty job_id retrieves latest receipt. wait_seconds 0..20 bounds each call. Never starts/approves/retries Codex, even after disconnects or unknown completion."""
        return jobs.status(job_id, wait_seconds)

    @server.prompt(name='study-save')
    def save_prompt() -> str:
        return INSTRUCTIONS + '\nThe user explicitly selected study-save. Prepare the faithful context and submit once.'

    @server.prompt(name='study-load')
    def load_prompt(topic: str) -> str:
        return INSTRUCTIONS + '\nThe user requested study-load for: ' + topic

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path.home()/'.config/study-save/config.json')
    args = parser.parse_args()
    execute = Backend(args.config)
    jobs = desktop_jobs(args.config, execute)
    def terminate(signum, frame):
        # SDK tools use worker threads: close them before unwinding the main loop.
        jobs.close()
        execute.close()
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    try:
        make_server(execute, jobs).run(transport='stdio')
    except KeyboardInterrupt:
        pass
    finally:
        jobs.close()
        execute.close()


if __name__ == '__main__':
    main()
