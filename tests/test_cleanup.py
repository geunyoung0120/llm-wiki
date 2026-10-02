import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import study_save as core


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.vault = self.root/'vault'; self.vault.mkdir()
        self.state = self.root/'state'; self.state.mkdir()

    def seed(self, before):
        for name, data in before.items():
            path=self.vault/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)

    def test_cleanup_backs_up_starter_and_blank_preserves_knowledge(self):
        before={'환영합니다!.md':b'Obsidian starter [[placeholder]]', 'blank.md':b'', 'knowledge.md':b'# Useful knowledge'}
        self.seed(before); after={'knowledge.md':before['knowledge.md']}
        reasons={'환영합니다!.md':{'reason':'Unmodified starter; no learning content'},'blank.md':{'reason':'Empty file'}}
        changes,backup=core._commit(self.vault,self.state,before,after,removals=reasons)
        self.assertEqual(set(changes),set(reasons)); self.assertEqual(core._read_notes(self.vault),after)
        with zipfile.ZipFile(backup) as archive:
            self.assertEqual(archive.read('notes/환영합니다!.md'),before['환영합니다!.md'])
            manifest=json.loads(archive.read('manifest.json'))
            self.assertEqual(set(manifest['removed']),set(reasons))
            self.assertEqual(manifest['removal_reasons'],reasons)

    def test_deletion_without_reason_is_rejected(self):
        before={'manual.md':b'Manual knowledge'}; self.seed(before)
        for reasons in ({}, {'manual.md':{'reason':''}}, {'other.md':{'reason':'unused'}}):
            with self.subTest(reasons=reasons), self.assertRaises(core.StudyError):
                core._commit(self.vault,self.state,before,{},removals=reasons)
            self.assertEqual(core._read_notes(self.vault),before)

    def test_cleanup_cannot_leave_a_link_to_removed_note(self):
        before={'target.md':b'# Target','ref.md':b'Read [[target]]'}; self.seed(before)
        with self.assertRaises(core.StudyError):
            core._commit(self.vault,self.state,before,{'ref.md':before['ref.md']},removals={'target.md':{'reason':'Merged'}})
        self.assertEqual(core._read_notes(self.vault),before)

    def test_cleanup_rolls_back_when_later_deletion_fails(self):
        before={'a.md':b'first','b.md':b'second'}; self.seed(before)
        original=core._atomic_remove
        def remove(path,expected,root):
            if path.name=='b.md':raise OSError('synthetic failure')
            return original(path,expected,root)
        with patch.object(core,'_atomic_remove',side_effect=remove), self.assertRaises(OSError):
            core._commit(self.vault,self.state,before,{},removals={n:{'reason':'unused'} for n in before})
        self.assertEqual(core._read_notes(self.vault),before)

    def test_external_edit_at_cleanup_capture_is_preserved(self):
        before={'a.md':b'old'}; self.seed(before); original=core.os.rename
        def rename(*args,**kwargs):
            (self.vault/'a.md').write_bytes(b'USER EDIT')
            return original(*args,**kwargs)
        with patch.object(core.os,'rename',side_effect=rename), self.assertRaises(core.StudyError):
            core._commit(self.vault,self.state,before,{},removals={'a.md':{'reason':'unused'}})
        self.assertEqual((self.vault/'a.md').read_bytes(),b'USER EDIT')

    def test_cleanup_metadata_reads_only_bounded_regular_file(self):
        path=self.root/'cleanup.json'; path.write_text(json.dumps({'a.md':{'reason':'unused'}}))
        self.assertEqual(core._cleanup_plan(self.root),{'a.md':{'reason':'unused'}})
        path.unlink(); path.symlink_to(self.vault/'a.md')
        with self.assertRaises(core.StudyError):core._cleanup_plan(self.root)

    def test_failed_restore_preserves_external_edit_and_reports_location(self):
        before={'a.md':b'old'}; self.seed(before); original=core.os.rename
        def rename(*args,**kwargs):
            (self.vault/'a.md').write_bytes(b'USER EDIT')
            return original(*args,**kwargs)
        with patch.object(core.os,'rename',side_effect=rename), patch.object(core.os,'link',side_effect=OSError('synthetic restore failure')):
            with self.assertRaises(core.RecoveryError) as raised:
                core._commit(self.vault,self.state,before,{},removals={'a.md':{'reason':'unused'}})
        held=list(self.vault.glob('.study-save-cleanup-*'))
        self.assertEqual(len(held),1); self.assertEqual(held[0].read_bytes(),b'USER EDIT')
        self.assertIn(str(held[0]),str(raised.exception)); self.assertFalse((self.vault/'a.md').exists())

    def test_cleanup_cannot_break_relative_markdown_links(self):
        before={'a note.md':b'# Target','folder/ref.md':b'Read [A](../a%20note.md#heading)'}; self.seed(before)
        with self.assertRaises(core.StudyError):
            core._commit(self.vault,self.state,before,{'folder/ref.md':before['folder/ref.md']},removals={'a note.md':{'reason':'unused'}})
        self.assertEqual(core._read_notes(self.vault),before)

    def test_common_save_reads_worker_cleanup_plan_and_reports_backup(self):
        from contextlib import redirect_stdout
        import io, sys
        before={'welcome.md':b'Starter [[example]]','knowledge.md':b'Useful content'}; self.seed(before)
        stub=self.root/'worker';stub.write_text('''#!/usr/bin/env python3\nimport sys,json\nfrom pathlib import Path\nargs=sys.argv;work=Path(args[args.index('-C')+1]);sys.stdin.read()\n(work/'notes/welcome.md').unlink()\n(work/'cleanup.json').write_text(json.dumps({'welcome.md':{'reason':'Starter only'}}))\nPath(args[args.index('-o')+1]).write_text('Removed starter; preserved knowledge.')\n''');stub.chmod(0o700)
        out=io.StringIO()
        with redirect_stdout(out):core.save(self.vault,self.state,str(stub),5,None,'Synthetic lesson','claude',cleanup=True)
        self.assertEqual(core._read_notes(self.vault),{'knowledge.md':before['knowledge.md']})
        self.assertIn('welcome.md: Starter only',out.getvalue());self.assertIn('Previous notes backup:',out.getvalue())
