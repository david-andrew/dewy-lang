"""Compiler test drivers, shared by content across workers and sessions.

Several test groups compile a compiler-sized driver program with the hosted
compiler before running their cases through it. Rebuilding one per pytest
worker and per session made those groups dominate the gate. A driver is
instead identified by everything its build can depend on: the driver source,
the hosted compiler and µDewy toolchain sources, the native compiler sources it
imports, the library, the build options and the Python version. The first
worker to need an identity builds it under a file lock; the others wait and
reuse the result, as do later sessions until any input changes. A failed
build is never recorded. A process keeps a shared lock on every entry it uses
until it exits, and pruning removes only entries nobody holds.

Each case still starts a fresh driver process with its own compiler session.
Only the executable is shared, never analysis state.

`DEWY_TEST_DRIVER_CACHE=0` disables sharing, so certification runs build
every driver independently. `DEWY_TEST_DRIVER_DIR` relocates the store
(default: `~/.cache/dewy/test-drivers`).

`DEWY_TEST_DRIVER_COMPILER=/absolute/path/to/dewy` selects native emission of driver
sources. It does not replace the hosted compiler calls used as test oracles.
The selected executable's content is part of every shared driver identity;
a native failure is a failure, never a silent hosted fallback. Leave it unset
for independent hosted-seeded validation (including release certification).
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import warnings
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_INPUT_DIRECTORIES = ('dewy', 'udewy', 'library')
_INPUT_SUFFIXES = {'.py', '.dewy', '.udewy', '.bin', '.c', '.h', '.json', '.s', '.S'}
_KEEP = 12
_inputs_digest: str | None = None
_held: dict[Path, object] = {}   # entry -> its lock file, held shared until exit


def _builder_identity() -> dict:
    configured = os.environ.get('DEWY_TEST_DRIVER_COMPILER')
    if not configured:
        return {'kind': 'hosted'}
    compiler = Path(configured).expanduser().resolve(strict=True)
    if not compiler.is_file() or not os.access(compiler, os.X_OK):
        raise ValueError(f'DEWY_TEST_DRIVER_COMPILER is not executable: {compiler}')
    return {'kind': 'native', 'path': str(compiler),
            'sha256': hashlib.sha256(compiler.read_bytes()).hexdigest()}


def _native_run(compiler: Path, source: Path, work: Path, arguments: list[str], route: str) -> str:
    backend = shutil.which('true')
    if backend is None:
        raise RuntimeError('native driver builds require the true executable')
    env = dict(os.environ, DEWY_LIBRARY_ROOT=str(ROOT / 'library'),
               DEWY_UDEWY=backend, DEWY_EMIT=route, DEWY_FAILURE_LOG='0')
    result = subprocess.run([str(compiler), *arguments, str(source)], cwd=work, env=env,
                            capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(f'native driver build failed ({result.returncode}): {source}\n'
                           f'{result.stdout}{result.stderr}')
    return result.stdout + result.stderr


def _native_codegen(compiler: Path, output: Path, source: Path, *,
                    target: str = 'x86_64', debug_locations: bool = True) -> None:
    """Use the CLI's text emitter; the test still chooses and runs its backend.

    The backend handoff is deliberately a no-op, as in the bootstrap script's
    deferred backend handoff. Requiring a newly emitted file independently of
    the exit status prevents a successful no-op from passing as an emission.
    Each build gets a fresh workspace, so neither stale artifacts nor concurrent
    builds can satisfy that check. Imports resolve from the original source.
    """
    from udewy.cache import cache_artifact

    source = source.resolve(strict=True)
    output = output.resolve()
    mode = ['debug', '--build'] if debug_locations else ['-c']
    with tempfile.TemporaryDirectory(prefix='dewy-driver-', dir=output.parent) as scratch:
        work = Path(scratch)
        emitted = work / cache_artifact(source, '.debug.udewy' if debug_locations else '.udewy', cwd=work)
        diagnostic = _native_run(compiler, source, work, [*mode, '--target', target], 'udewy')
        if not emitted.is_file() or not emitted.stat().st_size:
            raise RuntimeError(f'native compiler did not emit driver source: {source}\n{diagnostic}')
        shutil.copyfile(emitted, output)


def _native_driver(compiler: Path, source: Path, work: Path, name: str) -> Path:
    """Build an execution-only driver directly, without a hosted backend pass."""
    from udewy.cache import cache_artifact

    source = source.resolve(strict=True)
    output = work.resolve() / f'{name}-driver.native'
    with tempfile.TemporaryDirectory(prefix='dewy-driver-', dir=work) as scratch:
        cwd = Path(scratch)
        binary = cwd / cache_artifact(source, cwd=cwd)
        diagnostic = _native_run(compiler, source, cwd, ['-c', '--target', 'x86_64'], 'native')
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError(f'native compiler did not build an executable driver: {source}\n{diagnostic}')
        shutil.copy2(binary, output)
    return output


def _toolchain_digest() -> str:
    """Every source a hosted driver build can read, hashed once per process."""
    global _inputs_digest
    if _inputs_digest is None:
        digest = hashlib.sha256()
        files = []
        for directory in _INPUT_DIRECTORIES:
            for path in (ROOT / directory).rglob('*'):
                parts = path.relative_to(ROOT).parts
                if not path.is_file() or path.suffix not in _INPUT_SUFFIXES:
                    continue
                if '__pycache__' in parts or '__dewycache__' in parts or 'tests' in parts:
                    continue
                files.append(path)
        for path in sorted(files):
            digest.update(str(path.relative_to(ROOT)).encode() + b'\0')
            digest.update(path.read_bytes() + b'\0')
        digest.update(sys.version.encode())
        _inputs_digest = digest.hexdigest()
    return _inputs_digest


def enabled() -> bool:
    return os.environ.get('DEWY_TEST_DRIVER_CACHE', '1') != '0'


def _store() -> Path:
    configured = os.environ.get('DEWY_TEST_DRIVER_DIR')
    return Path(configured) if configured else Path.home() / '.cache/dewy/test-drivers'


def _isolated(build: Callable[[], Path]) -> Path:
    """Run `build` in a forked child and return the path it produced.

    A driver is a compiler-sized hosted build. In-process, the hosted
    compiler's resident state from every build stayed in the long-lived xdist
    worker (one worker grew past 9 GB near the end of the suite, which ran
    16 GB CI runners out of memory). The child gets the closure without
    pickling, and its memory goes back to the system when it exits.
    """
    read, write = os.pipe()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)   # fork in a threaded xdist worker
        pid = os.fork()
    if pid == 0:
        os.close(read)
        status = 0
        try:
            outcome: object = str(build())
        except BaseException as error:
            status = 1
            try:
                pickle.dumps(error)
                outcome = (error, traceback.format_exc())
            except Exception:
                outcome = (RuntimeError(str(error)), traceback.format_exc())
        with os.fdopen(write, 'wb') as channel:
            pickle.dump(outcome, channel)
        os._exit(status)
    os.close(write)
    with os.fdopen(read, 'rb') as channel:
        data = channel.read()
    os.waitpid(pid, 0)
    if not data:
        raise RuntimeError('driver build child exited without a result')
    outcome = pickle.loads(data)
    if isinstance(outcome, tuple):
        error, child_traceback = outcome
        error.add_note(f'raised in the driver build child process:\n{child_traceback}')
        raise error
    return Path(outcome)


def isolated_codegen(output: Path, source: Path, **options) -> None:
    """Write µDewy for `source`, using the selected driver compiler.

    Tests that build a compiler-sized driver themselves call this instead of
    `output.write_text(codegen(SrcFile.from_path(source)))`, so the hosted
    compile's memory is released when it ends (see `_isolated`).
    """
    builder = _builder_identity()
    if builder['kind'] == 'native':
        _native_codegen(Path(builder['path']), output, source, **options)
        return
    def build() -> Path:
        from dewy.backend.udewy import codegen
        from dewy.reporting import SrcFile
        output.write_text(codegen(SrcFile.from_path(source), **options))
        return output
    _isolated(build)


def shared_driver(name: str, source: Path, options: dict, build: Callable[[], Path], *, located: bool = True) -> Path:
    """The driver built by `build()` for `source` under `options`, shared by identity.

    `source` is the driver's entry file. Its absolute path is part of the
    identity when relative imports resolve from it (`located`); a generated
    source with only absolute imports may live anywhere. `build` compiles
    the driver and returns the executable; it runs at most once per identity
    across concurrent workers.
    """
    if not enabled():
        return _isolated(build)
    builder = _builder_identity()
    identity = hashlib.sha256(json.dumps({
        'name': name, 'source': str(source.resolve()) if located else None, 'text': source.read_text(),
        'options': options, 'inputs': _toolchain_digest(), 'builder': builder,
    }, sort_keys=True).encode()).hexdigest()[:32]
    entry = _store() / f'{name}-{identity}'
    executable = entry / 'driver'
    if entry not in _held:
        lock = _lock(entry, fcntl.LOCK_SH)
        if not executable.is_file():
            # Only a missing driver needs the exclusive lock: no process
            # holds an entry shared before its driver exists.
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
            lock = _lock(entry, fcntl.LOCK_EX)
            try:
                if not executable.is_file():
                    built = _isolated(build)
                    staged = entry / 'driver.partial'
                    shutil.copy2(built, staged)
                    os.replace(staged, executable)
                    (entry / 'identity.json').write_text(json.dumps({
                        'name': name, 'source': str(source), 'options': options,
                        'inputs': _toolchain_digest(), 'builder': builder, 'built': time.time(),
                    }, indent=2))
            except BaseException:
                lock.close()
                raise
            fcntl.flock(lock, fcntl.LOCK_SH)
        _held[entry] = lock
    os.utime(entry)
    _prune(entry.parent)
    return executable


def _lock(entry: Path, mode: int):
    """The entry's lock file, locked in `mode`, retrying if pruning removed it meanwhile."""
    while True:
        entry.mkdir(parents=True, exist_ok=True)
        lock = open(entry / '.lock', 'a')
        fcntl.flock(lock, mode)
        try:
            if os.path.samestat(os.fstat(lock.fileno()), os.stat(entry / '.lock')):
                return lock
        except FileNotFoundError:
            pass
        lock.close()


def _prune(store: Path) -> None:
    """Keep the most recently used identities; drop the rest."""
    entries = []
    for path in store.iterdir():
        try:
            if path.is_dir():
                entries.append((path.stat().st_mtime, path))
        except FileNotFoundError:
            continue
    entries.sort(reverse=True)
    for _, stale in entries[_KEEP:]:
        if stale in _held:
            continue
        try:
            with open(stale / '.lock', 'a') as lock:
                # A holder anywhere (shared or building) keeps the entry.
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                shutil.rmtree(stale, ignore_errors=True)
        except (BlockingIOError, FileNotFoundError):
            continue


def compiler_driver(name: str, source: Path, work: Path, *, debug_locations: bool = False,
                    debug_info: bool = False, located: bool = True) -> Path:
    """Build an execution driver directly; metadata requests retain the text route.

    Test assertions run the executable, not its debug metadata. Hosted mode
    remains independently seeded; native mode does not rebuild that executable
    a second time through the hosted µDewy backend.
    """
    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point

    builder = _builder_identity()
    direct = builder['kind'] == 'native' and not debug_locations and not debug_info

    def build() -> Path:
        if direct:
            return _native_driver(Path(builder['path']), source, work, name)
        output = work / f'{name}-driver.udewy'
        isolated_codegen(output, source, debug_locations=debug_locations)
        assert entry_point(output, [], EntryPointOptions(compile_only=True, debug_info=debug_info)) == 0
        return cache_artifact(output).resolve()
    return shared_driver(name, source, {'debug_locations': debug_locations, 'debug_info': debug_info,
                                       'direct': direct}, build, located=located)
