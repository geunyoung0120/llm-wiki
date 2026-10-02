#!/usr/bin/env python3
"""Install foreground commands and shared manual-only skills without overwrites."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tomllib

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', default=str(Path.home()), help='installation home; override only for isolated tests')
    parser.add_argument('--vault', help='existing Obsidian vault; required on first install')
    parser.add_argument('--language', default='English', help='language for new notes and agent reports')
    args = parser.parse_args(argv)
    home = Path(args.home).expanduser().resolve()
    config_path = home / '.config/study-save/config.json'
    try:
        links = {}
        for name in ('study-save', 'study-load'):
            links[home / '.local/bin' / name] = ROOT / 'bin/study-save'
            for base in ('.codex/skills', '.agents/skills', '.claude/skills'):
                links[home / base / name] = ROOT / 'skills' / name
        # Validate all destinations before making any changes.
        for path, target in links.items():
            if path.exists() or path.is_symlink():
                if not path.is_symlink() or path.resolve() != target.resolve():
                    raise ValueError(f'Refusing to overwrite existing command or skill: {path}')
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding='utf-8'))
            vault = Path(config['vault']).expanduser()
            if not vault.is_absolute():
                vault = config_path.parent / vault
            vault = vault.resolve()
            if args.vault and Path(args.vault).expanduser().resolve() != vault:
                raise ValueError('Existing config selects a different vault; edit its vault field deliberately.')
            if not vault.is_dir():
                raise ValueError(f'Configured vault does not exist: {vault}')
        else:
            if args.vault:
                vault = Path(args.vault).expanduser().resolve()
                if not vault.is_dir():
                    raise ValueError('--vault must name an existing directory.')
            else:
                raise ValueError('First installation requires --vault pointing to an existing Obsidian vault.')
            executable = shutil.which('codex')
            if not executable:
                raise ValueError('Codex CLI must be installed and logged in first.')
            model_config = home / '.codex/config.toml'
            selected_model = None
            if model_config.is_file():
                selected_model = tomllib.loads(model_config.read_text(encoding='utf-8')).get('model')
            if not args.language.strip() or len(args.language) > 64 or any(ord(c) < 32 for c in args.language):
                raise ValueError('--language must be a nonempty language name of at most 64 characters.')
            if not (vault / '.obsidian').is_dir() and any(p.is_dir() and not p.is_symlink() and (p / '.obsidian').is_dir() for p in vault.iterdir()):
                raise ValueError('--vault points above an Obsidian vault; select the actual root.')
            config = {'vault': str(vault), 'codex': executable, 'timeout_seconds': 600, 'language': args.language.strip(), 'cleanup': False}
            if isinstance(selected_model, str) and selected_model:
                config['model'] = selected_model
            vault.mkdir(exist_ok=True)
            config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with config_path.open('x', encoding='utf-8') as handle:
                json.dump(config, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            config_path.chmod(0o600)
        for path, target in links.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_symlink():
                path.symlink_to(target, target_is_directory=target.is_dir())
        print(f'Shared vault: {vault}')
        print(f'Shared config: {config_path}')
        print(f'Commands: {home / ".local/bin/study-save"}, {home / ".local/bin/study-load"}')
        print('Manual-only local skills installed. Start a new host session to discover them.')
        print('Optional Claude Desktop: create .venv, install requirements-chat.lock, then run install_desktop.py.')
        print('No automatic saving, scheduled work, watchers, or automatic retries installed.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'install: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
