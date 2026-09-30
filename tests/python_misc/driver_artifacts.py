"""Hosted-built native test drivers, shared by content across workers and sessions.

Several test groups compile a compiler-sized driver program with the hosted
compiler before running their cases through it. Rebuilding one per pytest
worker and per session made those groups dominate the gate. A driver is
instead identified by everything its build can depend on: the driver source,
the hosted compiler and µDewy toolchain sources, the native compiler sources it
imports, the library, the build options and the Python version. The first
worker to need an identity builds it under a file lock; the others wait and
reuse the result, as do later sessions until any input changes. A failed
build is never recorded.

Each case still starts a fresh driver process with its own compiler session.
Only the executable is shared, never analysis state.

`DEWY_TEST_DRIVER_CACHE=0` disables sharing, so certification runs build
every driver independently. `DEWY_TEST_DRIVER_DIR` relocates the store
(default: `~/.cache/dewy/test-drivers`).
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
_INPUT_DIRECTORIES = ('dewy', 'udewy', 'library')
_INPUT_SUFFIXES = {'.py', '.dewy', '.udewy', '.bin', '.c', '.h', '.json', '.s', '.S'}
_KEEP = 12
_inputs_digest: str | None = None


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


def shared_driver(name: str, source: Path, options: dict, build: Callable[[], Path], *, located: bool = True) -> Path:
    """The driver built by `build()` for `source` under `options`, shared by identity.

    `source` is the driver's entry file. Its absolute path is part of the
    identity when relative imports resolve from it (`located`); a generated
    source with only absolute imports may live anywhere. `build` compiles
    the driver and returns the executable; it runs at most once per identity
    across concurrent workers.
    """
    if not enabled():
        return build()
    identity = hashlib.sha256(json.dumps({
        'name': name, 'source': str(source.resolve()) if located else None, 'text': source.read_text(),
        'options': options, 'inputs': _toolchain_digest(),
    }, sort_keys=True).encode()).hexdigest()[:32]
    entry = _store() / f'{name}-{identity}'
    executable = entry / 'driver'
    entry.mkdir(parents=True, exist_ok=True)
    with open(entry / '.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not executable.is_file():
            built = build()
            staged = entry / 'driver.partial'
            shutil.copy2(built, staged)
            os.replace(staged, executable)
            (entry / 'identity.json').write_text(json.dumps({
                'name': name, 'source': str(source), 'options': options,
                'inputs': _toolchain_digest(), 'built': time.time(),
            }, indent=2))
    os.utime(entry)
    _prune(entry.parent)
    return executable


def _prune(store: Path) -> None:
    """Keep the most recently used identities; drop the rest."""
    entries = sorted((path for path in store.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime, reverse=True)
    for stale in entries[_KEEP:]:
        lock_path = stale / '.lock'
        try:
            with open(lock_path, 'w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                shutil.rmtree(stale, ignore_errors=True)
        except (BlockingIOError, FileNotFoundError):
            continue


def hosted_driver(name: str, source: Path, work: Path, *, debug_locations: bool = True, debug_info: bool = True) -> Path:
    """Compile the driver `source` with the hosted compiler, shared by identity."""
    from dewy.backend.udewy import codegen
    from dewy.reporting import SrcFile
    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point

    def build() -> Path:
        output = work / f'{name}-driver.udewy'
        output.write_text(codegen(SrcFile.from_path(source), debug_locations=debug_locations))
        assert entry_point(output, [], EntryPointOptions(compile_only=True, debug_info=debug_info)) == 0
        return cache_artifact(output).resolve()
    return shared_driver(name, source, {'debug_locations': debug_locations, 'debug_info': debug_info}, build)
