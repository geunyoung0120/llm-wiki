import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
INSTALL = PROJECT / "install.py"

class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="study-install-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home";self.home.mkdir()
        self.vault = Path(self.temp.name) / "vault";self.vault.mkdir()
        fake_bin = Path(self.temp.name) / "bin"; fake_bin.mkdir()
        fake = fake_bin / "codex"; fake.write_text("#!/bin/sh\nexit 0\n"); fake.chmod(0o700)
        self.env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ.get('PATH', os.defpath))

    def run_install(self):
        self.assertTrue(INSTALL.is_file(), "Installer is not implemented yet")
        return subprocess.run([sys.executable,str(INSTALL),'--home',str(self.home),'--vault',str(self.vault)],capture_output=True,text=True,env=self.env)

    def test_installs_one_shared_vault_and_manual_skill_links(self):
        r = self.run_install()
        self.assertEqual(r.returncode,0,r.stderr)
        config = json.loads((self.home/'.config/study-save/config.json').read_text())
        self.assertEqual(config['vault'],str(self.vault.resolve()))
        for name in ['study-save','study-load']:
            self.assertTrue((self.home/'.local/bin'/name).is_symlink())
            a = (self.home/'.codex/skills'/name).resolve()
            b = (self.home/'.claude/skills'/name).resolve()
            self.assertEqual(a,b)
            self.assertTrue((a/'SKILL.md').is_file())
        self.assertFalse(list(self.vault.iterdir()))

    def test_install_is_idempotent(self):
        r = self.run_install();self.assertEqual(r.returncode,0,r.stderr)
        config = self.home/'.config/study-save/config.json';before = config.read_bytes()
        r = self.run_install();self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(config.read_bytes(),before)

    def test_does_not_overwrite_existing_command(self):
        command = self.home/'.local/bin/study-save';command.parent.mkdir(parents=True)
        command.write_text('existing user command')
        r = self.run_install()
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(command.read_text(),'existing user command')
        self.assertFalse((self.home/'.config/study-save/config.json').exists())
        self.assertFalse((self.home/'.local/bin/study-load').exists())

    def test_preserves_existing_config_and_model(self):
        config = self.home/'.config/study-save/config.json';config.parent.mkdir(parents=True)
        data = {'vault':str(self.vault),'codex':'codex','model':'my-existing-choice'}
        config.write_text(json.dumps(data));before=config.read_bytes()
        r=self.run_install();self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(config.read_bytes(),before)

    def test_preserves_existing_skill_directory(self):
        skill=self.home/'.claude/skills/study-save';skill.mkdir(parents=True)
        (skill/'SKILL.md').write_text('existing skill')
        r=self.run_install();self.assertNotEqual(r.returncode,0)
        self.assertEqual((skill/'SKILL.md').read_text(),'existing skill')
        self.assertFalse((self.home/'.local/bin/study-save').exists())

if __name__ == '__main__':
    unittest.main()
