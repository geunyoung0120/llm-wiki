#!/usr/bin/env python3
"""Read-only local setup checks. Never starts a save/load or changes config."""
import argparse
import subprocess
import sys
from types import SimpleNamespace
from study_save import DEFAULT_CONFIG, StudyError, _settings

REQUIRED_FLAGS = ('--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check', '--sandbox', '--output-last-message')

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    try:
        if sys.version_info < (3, 11):
            raise StudyError('Python 3.11+ is required.')
        if sys.platform != 'darwin':
            print('WARNING: this release is tested on macOS only.')
        vault, state, executable, timeout, model, language, cleanup = _settings(SimpleNamespace(config=args.config, vault=None))
        help_result = subprocess.run([executable, 'exec', '--help'], capture_output=True, text=True, timeout=15)
        missing = [f for f in REQUIRED_FLAGS if f not in help_result.stdout]
        if help_result.returncode or missing:
            raise StudyError('Codex CLI is incompatible or unavailable. Missing required flags: ' + ', '.join(missing))
        auth = subprocess.run([executable, 'login', 'status'], capture_output=True, text=True, timeout=15)
        if auth.returncode:
            raise StudyError('Codex is not logged in. Run codex login yourself, then retry diagnostics.')
        print('PASS: config, vault path, Python, Codex flags, and login status.')
        print(f'Vault: {vault}\nLanguage: {language}\nCleanup: {cleanup}\nCodex timeout: {timeout:g}s')
        print('No knowledge operation was started. No files were modified.')
        return 0
    except (StudyError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
