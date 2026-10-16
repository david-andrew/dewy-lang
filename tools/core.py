"""Build and use the current compact core from this checkout.

    python3 -m tools.core test [-k expression]
    python3 -m tools.core build example.dewy --release -o /tmp/example
    python3 -m tools.core --bootstrap test
    python3 -m tools.core path
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from tools.sloppy_core.build import ROOT, build

CACHE = ROOT / '__dewycache__' / 'compact-core'
TESTS = (
    'tests/python_misc/test_sloppy_core.py',
    'tests/python_misc/test_sloppy_core_editor.py',
    'tests/python_misc/test_sloppy_core_watch.py',
    'tests/python_misc/test_sloppy_core_upstream.py',
    'tests/python_misc/test_core_dev.py',
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity(root: Path) -> str:
    paths = [root / 'tools/sloppy_core/build.py']
    core = root / 'core'
    paths.extend(core / name for name in ('LICENSE', 'NOTICE', 'UPSTREAM.json'))
    for directory in ('compiler', 'lib', 'stage0', 'bootstrap'):
        paths.extend(path for path in (core / directory).rglob('*')
                     if path.is_file() and path.name != 'sloppy0' and '__pycache__' not in path.parts)
    identity = hashlib.sha256()
    for path in sorted(paths):
        identity.update(str(path.relative_to(root)).encode())
        identity.update(b'\0')
        identity.update(bytes.fromhex(digest(path)))
    return identity.hexdigest()


def cached_state(cache: Path) -> tuple[dict, Path | None]:
    try:
        state = json.loads((cache / 'current.json').read_text())
        binary = (cache / state['binary']).resolve(strict=True)
        if not binary.is_relative_to(cache.resolve()) or digest(binary) != state['binary_sha256']:
            return {}, None
        return state, binary
    except (OSError, ValueError, KeyError, TypeError):
        return {}, None


def toolchain(*, bootstrap: bool = False, cache: Path = CACHE, root: Path = ROOT) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    # Serialize cache publication/builds. Running commands retain an immutable
    # toolchain directory when another invocation rebuilds newer sources.
    with (cache / 'build.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        identity = source_identity(root)
        state, seed = cached_state(cache)
        if not bootstrap and seed is not None and state.get('source_identity') == identity:
            return seed
        output = cache / f'build-{time.time_ns()}'
        from_c = bootstrap or seed is None
        print('Building the compact core' + (' from C…' if from_c else ' from the previous core…'),
              file=sys.stderr, flush=True)
        binary = build(output, bootstrap=from_c, seed=None if from_c else seed)
        # A source edit during compilation must not publish a misleading cache
        # hit. The built snapshot remains available for diagnosis/reuse manually.
        if source_identity(root) != identity:
            raise RuntimeError('Compiler sources changed during the build; run the command again.')
        state = {'source_identity': identity, 'binary': str(binary.relative_to(cache)),
                 'binary_sha256': digest(binary)}
        temporary = cache / 'current.json.tmp'
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        temporary.replace(cache / 'current.json')
        print(f'Compiler ready: {binary}', file=sys.stderr, flush=True)
        return binary


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--bootstrap', action='store_true', help='force an independent build from C')
    cli.add_argument('command', choices=('path', 'test', 'build', 'check', 'run', 'watch', 'new', 'lsp'))
    cli.add_argument('arguments', nargs=argparse.REMAINDER, help='arguments for pytest or the compiler')
    args = cli.parse_args(argv)
    if args.command == 'path' and args.arguments:
        cli.error('path takes no additional arguments')
    try:
        binary = toolchain(bootstrap=args.bootstrap)
    except (OSError, RuntimeError) as error:
        print(f'dewy development: {error}', file=sys.stderr)
        return 1
    if args.command == 'path':
        print(binary)
        return 0
    env = os.environ.copy()
    if args.command == 'test':
        python = ROOT / '.venv/bin/python'
        if not python.exists():
            python = Path(sys.executable)
        env = {k: v for k, v in env.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
        env.update(DEWY_CORE_COMPILER=str(binary), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
        command = [str(python), '-m', 'pytest', '-q', '-o', 'addopts=', *TESTS, *args.arguments]
        return subprocess.call(command, cwd=ROOT, env=env)
    # The compiler owns the terminal/LSP streams and receives signals directly;
    # there is no wrapper process to leave a watcher or language server orphaned.
    os.execve(binary, [str(binary), args.command, *args.arguments], env)


if __name__ == '__main__':
    raise SystemExit(main())
