import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
ENTRY = PROJECT / "bin" / "study-save"

FAKE_CODEX = r"""#!/usr/bin/env python3
import os, sys
from pathlib import Path
args = sys.argv[1:]
root = Path(args[args.index('-C') + 1])
notes = root / 'notes'
report = Path(args[args.index('-o') + 1])
prompt = sys.stdin.read()
mode = os.environ.get('FAKE_MODE', 'new')
marker = Path(os.environ['FAKE_MARKER'])
marker.write_text(prompt)
if mode == 'fail':
    (notes / 'bad.md').write_text('partial')
    sys.exit(9)
if mode == 'timeout':
    import time
    time.sleep(10)
if mode == 'new':
    (notes / '캐시.md').write_text('# 캐시\n\n캐시는 재사용 가능한 데이터를 저장한다.\n\n## 남은 질문\n- 무효화 전략은?\n')
if mode == 'update':
    (notes / '캐시.md').write_text('# 캐시\n\n캐시는 항상 최신 데이터를 보장하지 않는다.\n')
if mode == 'delete':
    (notes / '캐시.md').unlink()
if mode == 'nonmarkdown':
    (notes / 'run.sh').write_text('echo no')
if mode == 'symlink':
    (notes / 'escape.md').symlink_to(Path(os.environ['FAKE_OUTSIDE']))
if mode == 'directory_symlink':
    (notes / 'escape').symlink_to(Path(os.environ['FAKE_OUTSIDE']).parent, target_is_directory=True)
if mode == 'hardlink':
    os.link(notes / '캐시.md', notes / 'copy.md')
if mode == 'hidden':
    (notes / '.obsidian').mkdir()
    (notes / '.obsidian' / 'prefs.md').write_text('bad')
if mode == 'reserved':
    (notes / 'AGENTS.md').write_text('bad')
if mode == 'concurrent':
    Path(os.environ['FAKE_REAL_NOTE']).write_text('USER EDIT')
    (notes / '캐시.md').write_text('AGENT EDIT')
if mode == 'empty_note':
    (notes / '캐시.md').write_text('')
if mode == 'broken_link':
    (notes / '새 개념.md').write_text('# 새 개념\n\n관련: [[없는 개념]]\n')
if mode == 'good_link':
    (notes / '새 개념.md').write_text('# 새 개념\n\n관련: [[캐시]]\n')
if mode == 'blank_preserved':
    (notes / '새 개념.md').write_text('# 새 개념\n\n새로운 학습 내용\n')
if mode == 'attachment':
    (notes / '캐시.md').write_text('# 캐시\n\n그림: ![[첨부.png]]\n')
if mode == 'temporary_reference':
    (notes / '새 개념.md').write_text(f'# 새 개념\n\n[캐시]({root}/notes/캐시.md)\n')
if mode == 'blank_report':
    report.write_text('')
else:
    report.write_text('학습 자료: 캐시의 역할과 미해결 질문' if 'READ-ONLY LOAD' in prompt else '캐시 개념을 통합했습니다.')
"""


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="study-save-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.state = self.root / "state"
        self.fake = self.root / "codex"
        self.fake.write_text(FAKE_CODEX)
        self.fake.chmod(0o755)
        self.marker = self.root / "called.txt"
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({"vault": str(self.vault), "state_dir": str(self.state), "codex": str(self.fake), "timeout_seconds": 5}))
        self.env = dict(os.environ, FAKE_MARKER=str(self.marker), FAKE_OUTSIDE=str(self.root / "outside.md"), FAKE_REAL_NOTE=str(self.vault / "캐시.md"))
        (self.root / "outside.md").write_text("DO NOT CHANGE")

    def run_cli(self, *args, mode="new", text="캐시를 공부했다.", command="save"):
        self.assertTrue(ENTRY.is_file(), "CLI entrypoint is not implemented yet")
        return subprocess.run([sys.executable, str(ENTRY), command, "--config", str(self.config), *args], input=text, text=True, capture_output=True, env=dict(self.env, FAKE_MODE=mode), timeout=15)

    def seed(self):
        (self.vault / "캐시.md").write_text("# 캐시\n\n기존 설명\n")
        (self.vault / "첨부.png").write_bytes(b"asset")
        (self.vault / ".obsidian").mkdir()
        (self.vault / ".obsidian" / "app.json").write_text("{}")

    def test_help_has_no_side_effects(self):
        r = self.run_cli("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.state.exists())

    def test_empty_context_does_not_invoke_codex(self):
        r = self.run_cli("--input", "-", text="  ")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("empty", r.stderr.lower())
        self.assertFalse(self.marker.exists())
        self.assertFalse(list(self.vault.iterdir()))

    def test_explicit_save_calls_codex_and_integrates_note(self):
        r = self.run_cli("--input", "-", "--source", "chatgpt")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("재사용", (self.vault / "캐시.md").read_text())
        self.assertIn("EXPLICIT SAVE", self.marker.read_text())
        self.assertIn("chatgpt", self.marker.read_text())
        self.assertEqual(set(p.name for p in self.vault.iterdir()), {"캐시.md"})

    def test_update_preserves_assets_and_settings_and_creates_backup(self):
        self.seed()
        before = (self.vault / "캐시.md").read_bytes()
        r = self.run_cli("--input", "-", mode="update")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("보장하지", (self.vault / "캐시.md").read_text())
        self.assertEqual((self.vault / "첨부.png").read_bytes(), b"asset")
        self.assertEqual((self.vault / ".obsidian" / "app.json").read_text(), "{}")
        import zipfile
        backups = list(self.state.rglob("*.zip"))
        self.assertEqual(len(backups), 1)
        with zipfile.ZipFile(backups[0]) as backup:
            self.assertEqual(backup.read("notes/캐시.md"), before)

    def test_duplicate_noop_does_not_create_backup(self):
        self.seed()
        before = (self.vault / "캐시.md").read_bytes()
        r = self.run_cli("--input", "-", mode="noop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.vault / "캐시.md").read_bytes(), before)
        self.assertFalse(list(self.state.rglob("*.zip")))

    def test_codex_failure_never_promotes_partial_changes(self):
        self.seed()
        before = (self.vault / "캐시.md").read_bytes()
        r = self.run_cli("--input", "-", mode="fail")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.vault / "캐시.md").read_bytes(), before)
        self.assertFalse((self.vault / "bad.md").exists())

    def test_codex_timeout_never_promotes_changes(self):
        data = json.loads(self.config.read_text());data["timeout_seconds"] = 0.1
        self.config.write_text(json.dumps(data))
        r = self.run_cli("--input", "-", mode="timeout")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(list(self.vault.iterdir()))

    def test_concurrent_user_edit_is_not_overwritten(self):
        self.seed()
        r = self.run_cli("--input", "-", mode="concurrent")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("changed", r.stderr.lower())
        self.assertEqual((self.vault / "캐시.md").read_text(), "USER EDIT")

    def test_rejects_unsafe_output_without_modifying_vault(self):
        self.seed()
        before = (self.vault / "캐시.md").read_bytes()
        for mode in ["delete", "nonmarkdown", "symlink", "directory_symlink", "hardlink", "hidden", "reserved", "empty_note"]:
            with self.subTest(mode=mode):
                r = self.run_cli("--input", "-", mode=mode)
                self.assertNotEqual(r.returncode, 0, mode)
                self.assertEqual((self.vault / "캐시.md").read_bytes(), before)
                self.assertFalse((self.vault / "escape.md").exists())
                self.assertFalse((self.vault / "run.sh").exists())
        self.assertEqual((self.root / "outside.md").read_text(), "DO NOT CHANGE")

    def test_existing_symlink_note_is_rejected_before_codex(self):
        (self.vault / "escape.md").symlink_to(self.root / "outside.md")
        r = self.run_cli("--input", "-")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_load_prints_context_without_vault_or_state_writes(self):
        self.seed()
        before = (self.vault / "캐시.md").read_bytes()
        r = self.run_cli("캐시", "--no-clipboard", mode="noop", command="load")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("학습 자료", r.stdout)
        self.assertIn("READ-ONLY LOAD", self.marker.read_text())
        self.assertEqual((self.vault / "캐시.md").read_bytes(), before)
        self.assertFalse(self.state.exists())

    def test_load_rejects_mutating_worker(self):
        self.seed()
        before = (self.vault / "캐시.md").read_bytes()
        r = self.run_cli("캐시", "--no-clipboard", mode="update", command="load")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.vault / "캐시.md").read_bytes(), before)

    def test_load_requires_nonempty_report(self):
        self.seed()
        r = self.run_cli("캐시", "--no-clipboard", mode="blank_report", command="load")
        self.assertNotEqual(r.returncode, 0)

    def test_empty_vault_load_does_not_invoke_codex(self):
        r = self.run_cli("캐시", "--no-clipboard", command="load")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no stored learning notes", r.stdout)
        self.assertFalse(self.marker.exists())

    def test_packet_file_input_and_vault_override(self):
        packet = self.root / "학습 내용.txt";packet.write_text("학습 근거와 남은 질문")
        other = self.root / "another";other.mkdir()
        r = self.run_cli("--input", str(packet), "--vault", str(other))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("학습 근거", self.marker.read_text())
        self.assertTrue((other / "캐시.md").exists())
        self.assertFalse(list(self.vault.iterdir()))

    def test_missing_vault_is_not_silently_created(self):
        r = self.run_cli("--input", "-", "--vault", str(self.root / "missing"))
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertFalse((self.root / "missing").exists())

    def test_wrapper_load_dispatch(self):
        self.assertTrue(ENTRY.is_file(), "CLI entrypoint is not implemented yet")
        link = self.root / "study-load";link.symlink_to(ENTRY)
        r = subprocess.run([sys.executable, str(link), "캐시", "--config", str(self.config), "--no-clipboard"], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.marker.exists())

    def test_load_alias_treats_save_as_topic_not_operation(self):
        self.seed()
        self.assertTrue(ENTRY.is_file())
        link = self.root / 'study-load';link.symlink_to(ENTRY)
        result = subprocess.run([sys.executable, str(link), 'save', '--config', str(self.config), '--no-clipboard'], capture_output=True, text=True, env=dict(self.env, FAKE_MODE='noop'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('READ-ONLY LOAD', self.marker.read_text())

    def test_new_broken_wikilink_is_rejected(self):
        self.seed()
        r = self.run_cli('--input', '-', mode='broken_link')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('link', r.stderr.lower())
        self.assertFalse((self.vault / '새 개념.md').exists())

    def test_resolvable_wikilink_is_promoted(self):
        self.seed()
        r = self.run_cli('--input', '-', mode='good_link')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('[[캐시]]', (self.vault / '새 개념.md').read_text())

    def test_existing_empty_note_does_not_block_other_knowledge(self):
        (self.vault / '빈 노트.md').write_text('')
        r = self.run_cli('--input', '-', mode='blank_preserved')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.vault / '빈 노트.md').read_bytes(), b'')

    def test_load_output_cannot_write_inside_vault(self):
        self.seed()
        r = self.run_cli('캐시', '--no-clipboard', '--output', str(self.vault / '자료.md'), mode='noop', command='load')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertFalse((self.vault / '자료.md').exists())

    def test_second_save_cannot_run_with_existing_lock(self):
        import fcntl
        import hashlib
        key = hashlib.sha256(os.fsencode(self.vault.resolve())).hexdigest()[:24]
        directory = self.state / key;directory.mkdir(parents=True)
        with (directory / 'save.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            r = self.run_cli('--input', '-')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_existing_attachment_link_is_allowed(self):
        self.seed()
        r = self.run_cli('--input', '-', mode='attachment')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('첨부.png', self.marker.read_text())

    def test_temporary_workspace_reference_is_not_stored(self):
        self.seed()
        r = self.run_cli('--input', '-', mode='temporary_reference')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.vault / '새 개념.md').exists())

    def test_interrupt_after_replacement_rolls_back(self):
        sys.path.insert(0, str(PROJECT))
        import study_save as ss
        from unittest.mock import patch
        before = {'a.md': b'old a', 'b.md': b'old b'}
        after = {'a.md': b'new a', 'b.md': b'new b'}
        for name, data in before.items():
            (self.vault / name).write_bytes(data)
        self.state.mkdir()
        real_write = ss._atomic_write
        interrupted = False
        def write_then_interrupt(path, data, **kwargs):
            nonlocal interrupted
            real_write(path, data, **kwargs)
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt()
        with patch.object(ss, '_atomic_write', side_effect=write_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                ss._commit(self.vault, self.state, before, after)
        self.assertEqual(ss._read_notes(self.vault), before)

    def test_load_output_parent_is_pinned_before_worker(self):
        sys.path.insert(0, str(PROJECT))
        import study_save as ss
        from unittest.mock import patch
        outside = self.root / 'output';outside.mkdir()
        parent = self.root / 'output-link';parent.symlink_to(outside, target_is_directory=True)
        def swapped(*args, **kwargs):
            parent.unlink();parent.symlink_to(self.vault, target_is_directory=True)
            return 'packet'
        with patch.object(ss, 'load', side_effect=swapped):
            code = ss.main(['load','topic','--config',str(self.config),'--no-clipboard','--output',str(parent/'packet.md')])
        self.assertEqual(code, 0)
        self.assertFalse((self.vault / 'packet.md').exists())
        self.assertEqual((outside / 'packet.md').read_text(), 'packet\n')

    def test_atomic_update_preserves_changed_target(self):
        sys.path.insert(0, str(PROJECT))
        import study_save as ss
        note = self.vault / 'a.md';note.write_bytes(b'USER LATEST')
        with self.assertRaises(ss.StudyError):
            ss._atomic_write(note, b'AGENT', expected=b'old')
        self.assertEqual(note.read_bytes(), b'USER LATEST')

    def test_atomic_create_never_overwrites_existing_note(self):
        sys.path.insert(0, str(PROJECT))
        import study_save as ss
        note = self.vault / 'a.md';note.write_bytes(b'USER LATEST')
        with self.assertRaises((ss.StudyError, FileExistsError)):
            ss._atomic_write(note, b'AGENT', expected=None)
        self.assertEqual(note.read_bytes(), b'USER LATEST')

    def test_atomic_swap_detects_edit_at_replacement_time(self):
        sys.path.insert(0, str(PROJECT))
        import study_save as ss
        from unittest.mock import patch
        note = self.vault / 'a.md';note.write_bytes(b'old')
        exchange = getattr(ss, '_exchange', None)
        self.assertIsNotNone(exchange, 'Atomic exchange is not implemented')
        first = True
        def edited(source, target, **kwargs):
            nonlocal first
            if first:
                first = False
                target.write_bytes(b'USER LATEST')
            return exchange(source, target, **kwargs)
        with patch.object(ss, '_exchange', side_effect=edited):
            with self.assertRaises(ss.StudyError):
                ss._atomic_write(note, b'AGENT', expected=b'old')
        self.assertEqual(note.read_bytes(), b'USER LATEST')

    def test_atomic_writer_does_not_follow_replaced_parent(self):
        sys.path.insert(0, str(PROJECT))
        import study_save as ss
        folder = self.vault / 'folder';folder.mkdir()
        outside = self.root / 'outside-folder';outside.mkdir()
        (outside / 'a.md').write_bytes(b'old')
        folder.rmdir();folder.symlink_to(outside, target_is_directory=True)
        with self.assertRaises((ss.StudyError, OSError)):
            ss._atomic_write(folder / 'a.md', b'AGENT', expected=b'old', root=self.vault)
        self.assertEqual((outside / 'a.md').read_bytes(), b'old')

    def test_displaced_read_error_preserves_latest_external_edit(self):
        sys.path.insert(0, str(PROJECT))
        import study_save as ss
        from unittest.mock import patch
        note = self.vault / 'a.md';note.write_bytes(b'old')
        exchange = getattr(ss, '_exchange', None)
        reader = getattr(ss, '_read_at', None)
        self.assertIsNotNone(reader, 'Descriptor-based read is not implemented')
        first = True
        def edited(source, target, **kwargs):
            nonlocal first
            if first:
                first = False;target.write_bytes(b'USER LATEST')
            return exchange(source, target, **kwargs)
        def fail_once(directory, name):
            if name.startswith('.study-save-'):
                raise OSError('injected displaced read failure')
            return reader(directory, name)
        self.state.mkdir()
        with patch.object(ss, '_exchange', side_effect=edited), patch.object(ss, '_read_at', side_effect=fail_once):
            with self.assertRaises((ss.StudyError, OSError)):
                ss._commit(self.vault, self.state, {'a.md':b'old'}, {'a.md':b'AGENT'})
        candidates = [p.read_bytes() for p in self.vault.iterdir() if p.is_file()]
        self.assertIn(b'USER LATEST', candidates)
        self.assertEqual(note.read_bytes(), b'USER LATEST')

    def test_new_note_rollback_preserves_edit_at_capture(self):
        sys.path.insert(0, str(PROJECT))
        import study_save as ss
        from unittest.mock import patch
        note = self.vault / 'a.md';note.write_bytes(b'AGENT')
        remover = getattr(ss, '_remove_created', None)
        self.assertIsNotNone(remover, 'Atomic capture rollback is not implemented')
        rename = ss.os.rename
        def edited(source, target, **kwargs):
            if source == 'a.md':
                note.write_bytes(b'USER LATEST')
            return rename(source, target, **kwargs)
        with patch.object(ss.os, 'rename', side_effect=edited):
            remover(note, b'AGENT', self.vault)
        self.assertEqual(note.read_bytes(), b'USER LATEST')

    def test_failed_second_note_rolls_back_new_first_note(self):
        sys.path.insert(0, str(PROJECT))
        import study_save as ss
        from unittest.mock import patch
        write = ss._atomic_write
        def fail_second(path, data, **kwargs):
            if path.name == 'b.md':
                raise OSError('injected second note failure')
            return write(path, data, **kwargs)
        self.state.mkdir()
        with patch.object(ss, '_atomic_write', side_effect=fail_second):
            with self.assertRaises(OSError):
                ss._commit(self.vault, self.state, {}, {'a.md': b'AGENT', 'b.md': b'AGENT'})
        self.assertFalse((self.vault / 'a.md').exists())
        self.assertFalse((self.vault / 'b.md').exists())


if __name__ == "__main__":
    unittest.main()

class VaultBoundaryTests(unittest.TestCase):
    def test_link_to_existing_empty_note_is_rejected(self):
        import study_save as core
        before={'empty.md':b''}
        after=dict(before, **{'new.md':b'# new\n\n[[empty]]\n'})
        with self.assertRaises(core.StudyError): core._validate_changes(before,after)

    def test_editing_note_must_fix_existing_broken_links(self):
        import study_save as core
        before={'note.md':b'# old\n\n[[missing]]\n'}
        after={'note.md':b'# updated\n\n[[missing]]\n'}
        with self.assertRaises(core.StudyError): core._validate_changes(before,after)

    def test_parent_of_obsidian_vault_is_rejected_before_codex(self):
        import argparse
        import study_save as core
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); vault=root/'vault'; (vault/'real' / '.obsidian').mkdir(parents=True)
            config=root/'config.json'; config.write_text(json.dumps({'vault':str(vault),'codex':sys.executable}))
            args=argparse.Namespace(config=str(config),vault=None)
            with self.assertRaises(core.StudyError): core._settings(args)
