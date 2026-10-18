"""Build and use the current compact core from this checkout.

    python3 -m tools.core test [-k expression]
    python3 -m tools.core test --quick
    python3 -m tools.core build example.dewy --release -o /tmp/example
    python3 -m tools.core fmt example.dewy
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

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '__dewycache__' / 'compact-core'
TESTS = (
    'tests/python_misc/test_sloppy_core.py',
    'tests/python_misc/test_sloppy_core_editor.py',
    'tests/python_misc/test_sloppy_core_format.py',
    'tests/python_misc/test_sloppy_core_network.py',
    'tests/python_misc/test_sloppy_core_package.py',
    'tests/python_misc/test_sloppy_core_testing.py',
    'tests/python_misc/test_sloppy_core_parallel.py',
    'tests/python_misc/test_sloppy_core_watch.py',
    'tests/python_misc/test_sloppy_core_upstream.py',
    'tests/python_misc/test_core_dev.py',
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(*args, **kwargs):
    # Most invocations reuse the toolchain; don't import bootstrap tooling then.
    from tools.sloppy_core.build import build as build_toolchain
    return build_toolchain(*args, **kwargs)


def source_paths(root: Path) -> list[Path]:
    paths = [root / 'tools/sloppy_core/build.py']
    core = root / 'core'
    paths.extend(core / name for name in ('LICENSE', 'NOTICE', 'UPSTREAM.json'))
    for directory in ('compiler', 'lib', 'stage0', 'bootstrap'):
        paths.extend(path for path in (core / directory).rglob('*')
                     if path.is_file() and path.name != 'sloppy0' and '__pycache__' not in path.parts)
    return sorted(paths)


def file_stamp(path: Path) -> list[int]:
    stat = path.stat()
    # ctime catches same-size writes even when a tool restores the old mtime;
    # inode/device catch replacement files. These are local cache hints only.
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
            stat.st_ctime_ns, stat.st_mode]


def source_stamp(root: Path) -> list:
    # Enumerate every time so new/deleted inputs invalidate the fast path too.
    return [[str(path.relative_to(root)), *file_stamp(path)] for path in source_paths(root)]


def source_identity(root: Path) -> str:
    identity = hashlib.sha256()
    for path in source_paths(root):
        identity.update(str(path.relative_to(root)).encode())
        identity.update(b'\0')
        identity.update(bytes.fromhex(digest(path)))
    return identity.hexdigest()


def cached_state(cache: Path) -> tuple[dict, Path | None]:
    try:
        state = json.loads((cache / 'current.json').read_text())
        binary = (cache / state['binary']).resolve(strict=True)
        if not binary.is_relative_to(cache.resolve()):
            return {}, None
        stamp = file_stamp(binary)
        if state.get('binary_stamp') != stamp and digest(binary) != state['binary_sha256']:
            return {}, None
        return state, binary
    except (OSError, ValueError, KeyError, TypeError):
        return {}, None


def publish_state(cache: Path, state: dict):
    temporary = cache / 'current.json.tmp'
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.replace(cache / 'current.json')


def test_runner_options(python: Path, arguments: list[str]) -> list[str]:
    explicit = any(arg.startswith(('-n', '--numprocesses')) for arg in arguments)
    # Focused iteration should not pay worker startup/collection costs. Explicit
    # pytest worker options still work despite disabling unrelated plugin autoload.
    if arguments and not explicit:
        return []
    workers = min(4, getattr(os, 'process_cpu_count', os.cpu_count)() or 1)
    if not explicit:
        if workers == 1:
            return []
        available = subprocess.run(
            [str(python), '-c', 'import importlib.util\nraise SystemExit(importlib.util.find_spec("xdist") is None)'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if available.returncode:
            return []
    options = ['-p', 'xdist.plugin', '-p', 'tools.sloppy_core.pytest_parallel', '--dist=loadgroup']
    if not explicit:
        options += ['-n', str(workers)]
    return options


def toolchain(*, bootstrap: bool = False, cache: Path = CACHE, root: Path = ROOT) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    # Serialize cache publication/builds. Running commands retain an immutable
    # toolchain directory when another invocation rebuilds newer sources.
    with (cache / 'build.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stamp = source_stamp(root)
        state, seed = cached_state(cache)
        if (not bootstrap and seed is not None and state.get('source_stamp') == stamp
                and state.get('binary_stamp') == file_stamp(seed)):
            return seed
        identity = source_identity(root)
        if not bootstrap and seed is not None and state.get('source_identity') == identity:
            state['source_stamp'] = stamp
            state['binary_stamp'] = file_stamp(seed)
            publish_state(cache, state)
            return seed
        output = cache / f'build-{time.time_ns()}'
        from_c = bootstrap or seed is None
        print('Building the compact core' + (' from C…' if from_c else ' from the previous core…'),
              file=sys.stderr, flush=True)
        binary = build(output, bootstrap=from_c, seed=None if from_c else seed)
        # A source edit during compilation must not publish a misleading cache
        # hit. The built snapshot remains available for diagnosis/reuse manually.
        if source_identity(root) != identity or source_stamp(root) != stamp:
            raise RuntimeError('Compiler sources changed during the build; run the command again.')
        state = {'source_identity': identity, 'binary': str(binary.relative_to(cache)),
                 'binary_stamp': file_stamp(binary), 'binary_sha256': digest(binary),
                 'source_stamp': stamp}
        publish_state(cache, state)
        print(f'Compiler ready: {binary}', file=sys.stderr, flush=True)
        return binary


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--bootstrap', action='store_true', help='force an independent build from C')
    cli.add_argument('command', choices=('path', 'test', 'build', 'check', 'run', 'watch', 'new', 'lsp', 'fmt', 'repl'))
    cli.add_argument('arguments', nargs=argparse.REMAINDER,
                     help='arguments for pytest or the compiler; test --quick selects the smoke suite')
    args = cli.parse_args(argv)
    if args.command == 'path' and args.arguments:
        cli.error('path takes no additional arguments')
    quick = args.command == 'test' and '--quick' in args.arguments
    if quick:
        if any(arg.startswith('-m') for arg in args.arguments):
            cli.error('--quick selects its own test marker; use -k to narrow the smoke suite')
        args.arguments = ['-m', 'core_quick', *(arg for arg in args.arguments if arg != '--quick')]
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
        if quick:
            print('Running the quick smoke suite (native/web, default/release).', file=sys.stderr)
        python = ROOT / '.venv/bin/python'
        if not python.exists():
            python = Path(sys.executable)
        env = {k: v for k, v in env.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
        env.update(DEWY_CORE_COMPILER=str(binary), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
        # A shared compiler/library error otherwise repeats the same failed
        # build across the gate. A later --maxfail=0 requests every failure.
        command = [str(python), '-m', 'pytest', '-q', '-o', 'addopts=', '--maxfail=1',
                   *test_runner_options(python, args.arguments), *TESTS, *args.arguments]
        return subprocess.call(command, cwd=ROOT, env=env)
    # The compiler owns the terminal/LSP streams and receives signals directly;
    # there is no wrapper process to leave a watcher or language server orphaned.
    os.execve(binary, [str(binary), args.command, *args.arguments], env)


if __name__ == '__main__':
    raise SystemExit(main())
