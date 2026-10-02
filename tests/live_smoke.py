"""Opt-in real Codex test, using a disposable vault with synthetic knowledge."""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(vault):
    return {p.relative_to(vault).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in vault.rglob('*') if p.is_file()}


@contextmanager
def preserve_clipboard(enabled):
    original = subprocess.run(['pbpaste'], capture_output=True, check=True).stdout if enabled else None
    try:
        yield
    finally:
        if enabled:
            subprocess.run(['pbcopy'], input=original, check=True)


def run(config, operation, *, packet=None, topic=None, clipboard=False):
    argv = [sys.executable, str(ROOT / 'bin/study-save'), operation, '--config', str(config)]
    if packet is not None:
        if clipboard:
            subprocess.run(['pbcopy'], input=packet.encode('utf-8'), check=True)
        else:
            argv += ['--input', '-']
        argv += ['--source', 'other']
    else:
        argv += [topic]
        if not clipboard:
            argv += ['--no-clipboard']
    result = subprocess.run(argv, input=None if clipboard else packet, text=True, capture_output=True, timeout=650)
    if result.returncode:
        raise AssertionError(result.stderr)
    print(result.stdout, flush=True)
    if clipboard and packet is None:
        actual = subprocess.run(['pbpaste'], capture_output=True, check=True).stdout.decode('utf-8')
        assert actual == result.stdout.rstrip('\n'), 'Clipboard differs from continuation packet'
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true', help='explicitly run real Codex on synthetic fixtures')
    parser.add_argument('--model', default=None)
    parser.add_argument('--clipboard', action='store_true', help='also test real macOS clipboard; restores original bytes in process')
    args = parser.parse_args()
    if not args.run:
        parser.error('This test calls real Codex. Pass --run explicitly.')
    with preserve_clipboard(args.clipboard), tempfile.TemporaryDirectory(prefix='study-save-live-') as tmp:
        home = Path(tmp)
        vault = home / 'vault'
        vault.mkdir()
        (vault / '수동 노트.md').write_text('# 수동 노트\n\n이 내용은 테스트 중 바꾸지 않는다.\n')
        (vault / '캐시 무효화.md').write_text('# 캐시 무효화\n\n캐시 무효화는 더 이상 유효하지 않은 캐시 데이터를 삭제하거나 교체하는 작업이다.\n\n## 남은 질문\n원본 DB 변경과 캐시 반영 사이의 순서는?\n')
        manual = (vault / '수동 노트.md').read_bytes()
        config = home / 'config.json'
        config.write_text(json.dumps({'vault': str(vault), 'state_dir': str(home / 'state'), 'model': args.model, 'language': 'Korean', 'cleanup': False}))
        first = '''[합성 테스트 학습 세션; 실제 사용자 경험이 아님]
주제: 캐시와 TTL
학습자는 처음에 캐시가 항상 최신 데이터를 준다고 생각했다. 설명과 예제로 이 생각을 정정했다.
정정 근거: 원본 DB가 갱신되어도 기존 캐시 엔트리가 만료되거나 무효화되지 않으면 오래된 값이 남을 수 있다.
이해한 내용: 캐시는 재사용할 데이터를 저장해서 반복 접근 비용을 줄인다. 캐시 적중은 저장된 값을 쓰고, 캐시 실패는 원본에서 가져오는 것이다.
TTL은 엔트리의 유효 시간을 정하는 만료 정책이고, 최신 데이터와의 일치를 항상 보장하는 장치는 아니다.
남은 질문: 여러 서버에 흩어진 캐시는 어떻게 함께 무효화할까?
출처: 이 합성 학습 세션의 설명·예제. 외부 출처는 제공되지 않았다.
'''
        print('LIVE 1/4: explicit first save', flush=True)
        run(config, 'save', packet=first, clipboard=args.clipboard)
        notes = [p for p in vault.rglob('*.md') if p.name != '수동 노트.md']
        assert notes, 'No knowledge notes created'
        all_text = '\n'.join(p.read_text() for p in notes)
        assert '최신' in all_text and 'TTL' in all_text, 'Missing key concepts'
        assert '질문' in all_text and '무효화' in all_text, 'Missing unresolved question'
        assert (vault / '수동 노트.md').read_bytes() == manual, 'Unrelated note changed'
        before_duplicate = digest(vault)
        print('LIVE 2/4: repeat identical evidence', flush=True)
        run(config, 'save', packet=first)
        assert digest(vault) == before_duplicate, 'Duplicate input changed existing knowledge'
        next_session = '''[합성 테스트 학습 세션; 실제 사용자 경험이 아님]
주제: 캐시 무효화와 TTL
지난 공부에서 남긴 질문을 조금 다뤘다. 이제 이해한 내용: 원본이 바뀌면 관련 캐시 엔트리를 삭제하거나 갱신하는 것이 캐시 무효화다.
TTL 만료는 일정 시간이 지난 엔트리를 무효하게 만드는 방법이지만, 시간이 지나기 전 오래된 값이 남을 수 있다.
오늘 정정한 오해: TTL을 60초로 설정하면 원본 수정 직후의 읽기도 최신이라고 생각했으나, 만료 전에는 오래된 캐시가 적중할 수 있음을 예제로 확인했다.
새 남은 질문: DB 쓰기와 캐시 삭제가 동시에 일어날 때 생기는 경쟁 상태를 어떻게 처리할까?
여러 서버 전체의 일관된 무효화 전략은 아직 해결하지 못했다. 해결됐다고 기록하지 말아야 한다.
기존 캐시 무효화 개념과 TTL의 관계를 이해하기 시작했다.
'''
        print('LIVE 3/4: related learning and correction', flush=True)
        run(config, 'save', packet=next_session)
        all_text = '\n'.join(p.read_text() for p in vault.rglob('*.md'))
        assert '경쟁' in all_text and '60' in all_text, 'New correction or unresolved question missing'
        assert '[[' in all_text, 'No relationships created between concept notes'
        assert (vault / '수동 노트.md').read_bytes() == manual, 'Unrelated note changed'
        before_load = digest(vault)
        print('LIVE 4/4: read-only load', flush=True)
        packet = run(config, 'load', topic='캐시, TTL, 캐시 무효화', clipboard=args.clipboard)
        assert 'TTL' in packet and '무효화' in packet, 'Missing continuation knowledge'
        assert digest(vault) == before_load, 'Load modified vault'
        print('LIVE PASS: first integration, duplicate no-op, correction + links, read-only load.', flush=True)
        print('Synthetic note paths:', ', '.join(sorted(before_load)), flush=True)
        if args.clipboard:
            print('Clipboard save input and load output: PASS', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
