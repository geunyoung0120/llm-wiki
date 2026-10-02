#!/usr/bin/env python3
"""Register the local Claude Desktop adapter, preserving existing settings."""
import argparse
import datetime
import json
import os
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parent


def install(home):
    home=Path(home)
    path=home/'Library/Application Support/Claude/claude_desktop_config.json'
    if path.is_symlink():
        raise ValueError('Claude config cannot be a symlink.')
    original=path.read_bytes() if path.exists() else None
    config=json.loads(original) if original else {}
    entry={'command':str(ROOT/'.venv/bin/python'),'args':[str(ROOT/'chat_bridge.py'),'--config',str(home/'.config/study-save/config.json')]}
    servers=config.setdefault('mcpServers',{})
    if 'study-save' in servers:
        if servers['study-save']!=entry:
            raise ValueError('An existing study-save MCP server belongs to another setup; refusing to overwrite.')
        return path
    if not Path(entry['command']).is_file():
        raise ValueError('Install requirements-chat.lock into .venv first.')
    servers['study-save']=entry
    path.parent.mkdir(parents=True,exist_ok=True)
    if original is not None:
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup=path.with_name(f'claude_desktop_config.study-save-{stamp}.backup.json')
        with backup.open('xb') as stream: stream.write(original)
        backup.chmod(0o600)
    fd,temp=tempfile.mkstemp(prefix='.study-save-config-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(config,stream,ensure_ascii=False,indent=2)
            stream.write('\n')
        if (path.read_bytes() if path.exists() else None)!=original:
            raise ValueError('Claude settings changed during install; retry deliberately.')
        os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home',type=Path,default=Path.home())
    args=parser.parse_args()
    print(install(args.home))
    print('Fully quit and reopen Claude Desktop to load the Study Save tools.')
