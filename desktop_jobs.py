"""Explicit desktop operations with bounded calls and recoverable result receipts.

No context is persisted. Reading a receipt never starts, retries, or approves work.
"""
from __future__ import annotations
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid

PENDING = {'queued', 'awaiting_approval', 'running'}
SOURCES = {'chatgpt', 'gpt', 'claude', 'codex', 'claude-code', 'other'}


class JobManager:
    def __init__(self, directory, approve, execute):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise ValueError('Job directory must be a real directory.')
        self.approve, self.execute = approve, execute
        self.lock = threading.RLock()
        self.events = {}
        self.closed = False

    def _write(self, receipt):
        fd, temporary = tempfile.mkstemp(prefix='.receipt-', dir=self.directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as file:
                json.dump(receipt, file, ensure_ascii=False)
                file.flush(); os.fsync(file.fileno())
            os.replace(temporary, self.directory / (receipt['job_id'] + '.json'))
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def _read(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch('[a-f0-9]{32}', job_id):
            return None
        path = self.directory / (job_id + '.json')
        if path.is_symlink(): return None
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            if (isinstance(value, dict) and value.get('job_id') == job_id
                and isinstance(value.get('status'), str)
                and value.get('status') in PENDING | {'done', 'cancelled', 'unknown'}
                and isinstance(value.get('created_ns'), int)
                and isinstance(value.get('output'), str)):
                return value
        except (OSError, ValueError): pass
        return None

    def _latest(self, operation=None):
        receipts = [self._read(p.stem) for p in self.directory.glob('*.json')]
        receipts = [r for r in receipts if r and (operation is None or r.get('operation') == operation)]
        return max(receipts, key=lambda r: r.get('created_ns', 0), default=None)

    def start(self, operation, text, source):
        if operation not in {'save', 'load'} or source not in SOURCES or not isinstance(text, str) or not text.strip() or len(text.encode('utf-8')) > 2*1024*1024:
            raise ValueError('A nonempty context/topic up to 2 MiB and a valid source are required.')
        with self.lock:
            if self.closed: raise RuntimeError('Bridge shutting down.')
            # Held for the whole job, including approval, across desktop connections.
            guard = os.open(self.directory / (operation + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                active_id = os.pread(guard, 64, 0).decode('ascii', errors='ignore')
                os.close(guard)
                return dict(status='busy', job_id=active_id, output='An operation is already running. No new operation was started. Check its existing job_id with study_status.')
            job_id = uuid.uuid4().hex
            os.ftruncate(guard, 0)
            os.write(guard, job_id.encode('ascii'))
            receipt = dict(job_id=job_id, operation=operation, source=source, owner_pid=os.getpid(), created_ns=time.time_ns(), status='awaiting_approval' if self.approve else 'queued', output='Waiting for fixture approval. Acceptance is not completion.' if self.approve else 'Request accepted for one execution. Acceptance is not completion. Retrieve this job with study_status.')
            event = threading.Event()
            self.events[job_id] = event
            try:
                self._write(receipt)
                thread = threading.Thread(target=self._run, args=(receipt.copy(), text, guard, event), daemon=True)
                thread.start()
            except BaseException:
                receipt.update(status='unknown', output='Could not start execution. Do not retry automatically.')
                try: self._write(receipt)
                except OSError: pass
                os.close(guard)
                self.events.pop(job_id, None)
                raise
            return receipt.copy()

    def _run(self, receipt, text, guard, event):
        try:
            if self.approve and not self.approve(receipt['operation'], text, receipt['source']):
                receipt.update(status='cancelled', output='Fixture approval declined; Codex was not started.')
            else:
                with self.lock:
                    if self.closed: raise RuntimeError('Bridge shutting down.')
                    receipt.update(status='running', output='Codex is processing the explicitly requested operation. Completion is not yet confirmed.')
                    self._write(receipt)
                result = self.execute(receipt['operation'], text, receipt['source'])
                receipt.update(status='done', output=result)
        except BaseException:
            # The backend may have promoted notes before an interrupted response.
            receipt.update(status='unknown', output='Execution was interrupted or failed; completion is unknown. Do not assume no writes. Inspect notes and backups; never retry automatically.')
        finally:
            receipt['finished_ns'] = time.time_ns()
            try:
                self._write(receipt)
            finally:
                os.close(guard)
                event.set()
                with self.lock: self.events.pop(receipt['job_id'], None)

    def status(self, job_id='', wait_seconds=0):
        if not isinstance(wait_seconds, (int, float)) or not 0 <= wait_seconds <= 20:
            raise ValueError('wait_seconds must be between 0 and 20.')
        receipt = self._read(job_id) if job_id else self._latest()
        if not receipt: return dict(status='not_found', output='No valid receipt found. This does not prove failure or absence of changes.')
        with self.lock: event = self.events.get(receipt['job_id'])
        if receipt['status'] in PENDING and wait_seconds:
            deadline = time.monotonic() + wait_seconds
            while receipt['status'] in PENDING and time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                completed = event.wait(remaining) if event else False
                if not event: time.sleep(min(.1, remaining))
                receipt = self._read(receipt['job_id']) or receipt
                # A finished worker may have failed to persist its final receipt.
                # Its released guard then yields unknown; never spin on a set event.
                if completed: break
        if receipt['status'] in PENDING and not self._active(receipt):
            receipt = dict(receipt, status='unknown', output='This job is no longer active. Completion is unknown. Do not replay it automatically.')
        return receipt

    def _active(self, receipt):
        operation = receipt.get('operation')
        if not isinstance(operation, str) or operation not in {'save', 'load'}: return False
        try:
            guard = os.open(self.directory / (operation + '.lock'), os.O_RDONLY | os.O_NOFOLLOW)
        except OSError: return False
        try:
            try:
                fcntl.flock(guard, fcntl.LOCK_SH | fcntl.LOCK_NB)
                return False
            except BlockingIOError:
                return os.pread(guard, 64, 0) == receipt['job_id'].encode('ascii')
        finally: os.close(guard)

    def close(self):
        with self.lock: self.closed = True
