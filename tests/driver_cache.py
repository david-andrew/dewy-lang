"""A persistent, content-addressed cache of the driver executables twin tests build.

A twin test links real compiler modules (or their frozen twins) into a driver and builds it with
the compiler under test, about the size of a self-build. The same module set recurs across tests,
pytest workers and runs, so a build is stored under `__dewycache__/driver-builds/<key[:2]>/<key>/`
and reused. The key is a hash of everything the build reads: the builder compiler's bytes, the
flags, the `DEWY_*` environment, the standard library's files and every module text (the compiler
sources, their substitutions and the driver). Any changed input therefore builds a new driver;
nothing is ever looked up by a name that an edit leaves unchanged.

Safety under concurrent workers: a build happens in a private stage directory, whose finished
contents are renamed into place (an entry either exists complete or not at all), and a per-key
file lock keeps two workers from building the same driver twice. Size: after each build the
least recently used entries are removed until the cache is within CAP_BYTES; an entry used in
the last PROTECT_SECONDS is never removed, so a running test does not lose its driver."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from tests.support import ROOT
from tools.filelock import lock_exclusive, try_lock_exclusive

CACHE = ROOT / '__dewycache__' / 'driver-builds'
CAP_BYTES = 12 << 30
PROTECT_SECONDS = 3600
STALE_STAGE_SECONDS = 86400
# Variables of the test runner that no build reads (the compiler is keyed by its bytes).
RUNNER_ONLY = {'DEWY_CORE_COMPILER', 'DEWY_CORE_LIB', 'DEWY_GATE_SLOT_HELD', 'DEWY_PYTEST_SHARD',
               'DEWY_NO_AUDIO'}

_digests: dict = {}


def file_digest(path: Path) -> bytes:
    """A file's SHA-256, remembered for this process while its size, time and inode stay."""
    stat = path.stat()
    stamp = (str(path), stat.st_size, stat.st_mtime_ns, stat.st_ino)
    if stamp not in _digests:
        _digests[stamp] = hashlib.sha256(path.read_bytes()).digest()
    return _digests[stamp]


def library_for(compiler: Path) -> Path:
    """The standard library the compiler would use: DEWY_CORE_LIB, else the one next to its bin/."""
    chosen = os.environ.get('DEWY_CORE_LIB')
    return Path(chosen) if chosen else compiler.parent.parent / 'lib'


def identity(compiler, modules, release=False, flags=()) -> str:
    """The hex key of one build."""
    compiler = Path(compiler)
    key = hashlib.sha256()

    def part(*items):
        for item in items:
            data = item if isinstance(item, bytes) else str(item).encode()
            key.update(len(data).to_bytes(8, 'little') + data)

    part('driver-cache-1', file_digest(compiler), bool(release), *map(str, flags))
    for name, value in sorted(os.environ.items()):
        if name.startswith('DEWY_') and name not in RUNNER_ONLY:
            part(name, value)
    library = library_for(compiler)
    if library.is_dir():
        for path in sorted(library.rglob('*')):
            if path.is_file():
                part(path.relative_to(library).as_posix(), file_digest(path))
    for name, text in sorted(modules.items()):
        part(name, text)
    return key.hexdigest()


def build_driver(compiler, modules, release=False, flags=(), cache=None, timeout=90) -> Path:
    """The executable built from `modules` ({file name: text}, one of them driver.jo)."""
    compiler = Path(compiler)
    cache = Path(cache) if cache else CACHE
    key = identity(compiler, modules, release, flags)
    entry = cache / key[:2] / key
    binary = entry / 'driver'
    if binary.exists():
        touch(entry)
        return binary
    entry.parent.mkdir(parents=True, exist_ok=True)
    with (entry.parent / f'{key}.lock').open('w') as lock:
        lock_exclusive(lock)
        if binary.exists():
            touch(entry)
            return binary
        (cache / 'stage').mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='build-', dir=cache / 'stage'))
        try:
            for name, text in modules.items():
                (stage / name).write_text(text)
            built = subprocess.run([compiler, 'build', stage / 'driver.jo', '-o', stage / 'driver',
                                    *(['--release'] if release else []), *flags],
                                   capture_output=True, text=True, timeout=timeout)
            assert built.returncode == 0, built.stdout + built.stderr
            # (only the executable is kept: the sources are rebuilt from the key's inputs)
            for name in modules:
                (stage / name).unlink()
            try:
                stage.rename(entry)
            except OSError:
                if not binary.exists():  # (else a worker that lost the lock to eviction published it first)
                    raise
        finally:
            shutil.rmtree(stage, ignore_errors=True)
    evict(cache)
    return binary


def touch(entry: Path):
    try:
        os.utime(entry)
    except OSError:
        pass


def evict(cache: Path, cap: int = CAP_BYTES, protect: float = PROTECT_SECONDS):
    """Remove the least recently used entries until the cache fits `cap` bytes."""
    with (cache / 'evict.lock').open('w') as lock:
        if not try_lock_exclusive(lock):
            return  # another worker is already doing this
        now = time.time()
        stage = cache / 'stage'
        if stage.is_dir():
            for leftover in stage.iterdir():
                if now - leftover.stat().st_mtime > STALE_STAGE_SECONDS:
                    shutil.rmtree(leftover, ignore_errors=True)
        entries = []
        for shard in cache.iterdir():
            if shard.is_dir() and shard.name != 'stage':
                for entry in shard.iterdir():
                    if entry.is_dir():
                        try:
                            entries.append((entry.stat().st_mtime, sum(f.stat().st_size for f in entry.iterdir()), entry))
                        except OSError:
                            pass  # removed by another worker meanwhile
        total = sum(size for _, size, _ in entries)
        for used, size, entry in sorted(entries):
            if total <= cap or now - used < protect:
                break
            shutil.rmtree(entry, ignore_errors=True)
            entry.with_name(entry.name + '.lock').unlink(missing_ok=True)
            total -= size
