import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import install_desktop

class DesktopInstallTests(unittest.TestCase):
    def test_preserves_other_config_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            path=home/'Library/Application Support/Claude/claude_desktop_config.json'
            path.parent.mkdir(parents=True)
            original={'theme':'dark','mcpServers':{'other':{'command':'other'}}}
            path.write_text(json.dumps(original))
            install_desktop.install(home)
            data=json.loads(path.read_text())
            self.assertEqual(data['theme'],'dark')
            self.assertEqual(data['mcpServers']['other'],original['mcpServers']['other'])
            self.assertIn('study-save',data['mcpServers'])
            backups=list(path.parent.glob('claude_desktop_config.study-save-*.backup.json'))
            self.assertEqual(len(backups),1)
            self.assertEqual(json.loads(backups[0].read_text()),original)
            install_desktop.install(home)
            self.assertEqual(len(list(path.parent.glob('*.backup.json'))),1)

    def test_refuses_other_existing_same_named_server(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            path=home/'Library/Application Support/Claude/claude_desktop_config.json'
            path.parent.mkdir(parents=True)
            original={'mcpServers':{'study-save':{'command':'someone-elses'}}}
            path.write_text(json.dumps(original))
            with self.assertRaises(ValueError): install_desktop.install(home)
            self.assertEqual(json.loads(path.read_text()),original)
