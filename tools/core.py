"""Build and use the current compact core from this checkout.

    python3 -m tools.core test [-k expression]
    python3 -m tools.core test --quick
    python3 -m tools.core build example.dewy --release -o /tmp/example
    python3 -m tools.core fmt example.dewy
    python3 -m tools.core --bootstrap test
    python3 -m tools.core path
    python3 -m tools.core cases [-k expression] [--update]
    python3 -m tools.core ladder [--update-ratchet]
    python3 -m tools.core speed [--base REV] [--checkpoint TAG] [--limit 1.0] [--release]
    python3 -m tools.core bench [-k WORDS] [--instructions] [--baseline REV]
    python3 -m tools.core fuzz [--seed N] [--count N] [--minutes M]
"""
from __future__ import annotations

import argparse
from tools.filelock import lock_exclusive
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '__dewycache__' / 'compact-core'
# Every tests/test_*.py runs; adding a test file needs no registration here.
# The largest files go first so parallel workers finish together.
TESTS = tuple(sorted((str(p.relative_to(ROOT)) for p in (ROOT / 'tests').glob('test_*.py')),
                     key=lambda name: -(ROOT / name).stat().st_size))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(*args, **kwargs):
    # Most invocations reuse the toolchain; don't import bootstrap tooling then.
    from tools.compiler.build import build as build_toolchain
    return build_toolchain(*args, **kwargs)


def source_paths(root: Path) -> list[Path]:
    paths = [root / 'tools/compiler/build.py']
    paths.extend(root / 'docs/origin' / name for name in ('LICENSE', 'NOTICE'))
    for directory in ('compiler', 'lib', 'stage0', 'bootstrap'):
        paths.extend(path for path in (root / directory).rglob('*')
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
    options = ['-p', 'xdist.plugin', '-p', 'tools.compiler.pytest_parallel', '--dist=loadgroup']
    if not explicit:
        options += ['-n', str(workers)]
    return options


def toolchain(*, bootstrap: bool = False, cache: Path = CACHE, root: Path = ROOT) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    # Serialize cache publication/builds. Running commands retain an immutable
    # toolchain directory when another invocation rebuilds newer sources.
    with (cache / 'build.lock').open('w') as lock:
        lock_exclusive(lock)
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


# The machine is shared by several worktrees: at most this many full gates run at once.
GATE_SLOTS = int(os.environ.get('DEWY_GATE_SLOTS', '2'))


def gate_slot():
    """Hold one of the machine-wide full-gate slots (a file lock) for the rest of the process."""
    from tools.filelock import try_lock_exclusive
    directory = Path.home() / '.cache' / 'dewy-gates'
    directory.mkdir(parents=True, exist_ok=True)
    waited = False
    while True:
        for slot in range(max(1, GATE_SLOTS)):
            handle = (directory / f'slot{slot}.lock').open('w')
            if try_lock_exclusive(handle):
                return handle
            handle.close()
        if not waited:
            print(f'Waiting for a full-gate slot ({GATE_SLOTS} run at once on this machine)…', file=sys.stderr, flush=True)
            waited = True
        time.sleep(5)


def gate_options(arguments: list[str]) -> tuple[str, int | None, bool, bool]:
    """The -k expression, -n workers, --maxfail=0 and whether pytest paths were named."""
    keyword, workers, every, paths = '', None, False, False
    items = iter(arguments)
    for arg in items:
        value = None
        if arg in ('-k', '-n', '--numprocesses', '--maxfail'):
            value = next(items, '')
        elif arg.startswith(('-k', '-n')) and not arg.startswith('--'):
            arg, value = arg[:2], arg[2:]
        elif arg.startswith(('--numprocesses=', '--maxfail=')):
            arg, value = arg.split('=', 1)
        elif arg in ('-m', '-p', '-o'):
            next(items, '')
        elif not arg.startswith('-'):
            paths = True
        if arg == '-k':
            keyword = value
        elif arg in ('-n', '--numprocesses') and value.isdigit():
            workers = int(value)
        elif arg == '--maxfail':
            every = value == '0'
    return keyword, workers, every, paths


def test(binary: Path, arguments: list[str], quick: bool) -> int:
    """Golden cases, then the ladder's core versions and ratchet, then pytest."""
    from tools import cases, ladder
    keyword, workers, every, paths = gate_options(arguments)
    if quick:
        print('Running the quick smoke suite (native/web, default/release).', file=sys.stderr)
    failed = False
    selected = 0
    if not paths:
        # Same worker default as pytest below; -n 0 means serial.
        count = workers if workers is not None else cases.default_workers()
        try:
            chosen = cases.discover(keyword=keyword, quick=quick)
        except cases.CaseError as error:
            print(f'cases: {error}', file=sys.stderr)
            return 2
        selected += len(chosen)
        if chosen:
            failed = cases.run(binary, chosen, workers=count or 1) != 0
        if not quick and not (failed and not every):
            programs = [n for n in ladder.load()['programs'] if cases.keyword_filter(keyword)(n)]
            selected += len(programs)
            if programs:
                failed = ladder.run(binary, keyword=keyword, workers=count or 1, scoreboard=False) != 0 or failed
        if not quick and not keyword and not (failed and not every):
            # The website's published examples (a few seconds): language changes must not break them.
            site = subprocess.call([sys.executable, str(ROOT / 'site/scripts/check_dewy_examples.py'),
                                    '--compiler', str(binary), '--scratch', str(CACHE / 'site-examples')], cwd=ROOT)
            failed = site != 0 or failed
        if failed and not every:
            return 1
    python = ROOT / '.venv/bin/python'
    if not python.exists():
        python = Path(sys.executable)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(DEWY_CORE_COMPILER=str(binary), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    if quick:
        arguments = ['-m', 'core_quick', *arguments]
    # A shared compiler/library error otherwise repeats the same failed
    # build across the gate. A later --maxfail=0 requests every failure.
    command = [str(python), '-m', 'pytest', '-q', '-o', 'addopts=', '--maxfail=1',
               *test_runner_options(python, arguments), *TESTS, *arguments]
    status = subprocess.call(command, cwd=ROOT, env=env)
    if status == 5 and selected:
        status = 0  # -k matched only golden cases or ladder programs
    return 1 if failed else status


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--bootstrap', action='store_true', help='force an independent build from C')
    cli.add_argument('command', choices=('path', 'test', 'cases', 'ladder', 'build', 'check', 'run', 'watch', 'new', 'lsp',
                                        'fmt', 'repl', 'speed', 'bench', 'fuzz'))
    cli.add_argument('arguments', nargs=argparse.REMAINDER,
                     help='arguments for pytest, speed, bench or the compiler; test --quick selects the smoke suite')
    args = cli.parse_args(argv)
    if args.command == 'path' and args.arguments:
        cli.error('path takes no additional arguments')
    if args.command == 'test' and any(a in ('-h', '--help') for a in args.arguments):
        print('usage: python3 -m tools.core [--bootstrap] test [--quick] [-k WORDS] [pytest options]\n\n'
              'Golden cases, then the acceptance ladder and site examples (full suite only), then pytest.\n'
              '--quick runs the smoke suite; -k selects cases, ladder programs and tests by keyword;\n'
              '--maxfail=0 reports every failure; other options go to pytest.')
        return 0
    quick = args.command == 'test' and '--quick' in args.arguments
    if quick:
        if any(arg.startswith('-m') for arg in args.arguments):
            cli.error('--quick selects its own test marker; use -k to narrow the smoke suite')
        args.arguments = [arg for arg in args.arguments if arg != '--quick']
    if args.command == 'fuzz' and any(a.split('=')[0] in ('--compiler', '--print') for a in args.arguments):
        from tools.compiler import dewy_fuzz
        return dewy_fuzz.main(args.arguments)
    if args.command in ('cases', 'ladder',) and any(a.split('=')[0] == '--compiler' for a in args.arguments):
        from importlib import import_module
        return import_module(f'tools.{args.command}').main(args.arguments)
    try:
        binary = toolchain(bootstrap=args.bootstrap)
    except (OSError, RuntimeError) as error:
        print(f'dewy development: {error}', file=sys.stderr)
        return 1
    if args.command == 'path':
        print(binary)
        return 0
    if args.command in ('cases', 'ladder',):
        from importlib import import_module
        return import_module(f'tools.{args.command}').main(args.arguments, binary)
    if args.command == 'fuzz':
        from tools.compiler import dewy_fuzz
        return dewy_fuzz.main(args.arguments, binary)
    if args.command in ('speed', 'bench'):
        from importlib import import_module
        try:
            return import_module(f'tools.compiler.{args.command}').main(args.arguments, binary)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f'{args.command}: {error}', file=sys.stderr)
            return 1
    env = os.environ.copy()
    if args.command == 'test':
        slot = None if quick or gate_options(args.arguments)[0] else gate_slot()
        try:
            return test(binary, args.arguments, quick)
        finally:
            if slot is not None:
                slot.close()
    # The compiler owns the terminal/LSP streams and receives signals directly;
    # there is no wrapper process to leave a watcher or language server orphaned.
    os.execve(binary, [str(binary), args.command, *args.arguments], env)


if __name__ == '__main__':
    raise SystemExit(main())
