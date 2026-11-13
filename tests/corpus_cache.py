"""Shared helpers for the corpus-wide twin tests: content-addressed results and worker-lifetime builds.

A corpus test that every xdist worker would repeat (generating the corpus, running its Python
oracle) stores the result under a digest of everything it was computed from, so a second worker or
a later run loads it. Keys cover the inputs and the test code; nothing else decides a hit."""
import atexit
import fcntl
import hashlib
import os
import pickle
import shutil
import subprocess
import tempfile
from pathlib import Path

SHARDS = 4


def digest(*parts):
    h = hashlib.sha256()
    for part in parts:
        data = part if isinstance(part, bytes) else repr(part).encode()
        h.update(len(data).to_bytes(8, 'little'))
        h.update(data)
    return h.hexdigest()[:32]


def cached(name, key, compute):
    """compute() once per key on this machine; concurrent callers wait for the first."""
    directory = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'dewy-test-corpus'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{name}-{key}.pkl'
    with (directory / f'{name}-{key}.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            try:
                return pickle.loads(path.read_bytes())
            except Exception:
                path.unlink(missing_ok=True)
        value = compute()
        temporary = path.with_suffix(f'.{os.getpid()}.tmp')
        temporary.write_bytes(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
        temporary.replace(path)
        return value


def shard_of(items, index, count=SHARDS):
    """Every count-th item from index: each shard samples the whole corpus."""
    return items[index::count]


_builds = {}
_scratch = []


def built_once(key, build):
    """build(directory) once per xdist worker process for key (compilers, drivers: read-only after)."""
    if key not in _builds:
        if not _scratch:
            _scratch.append(Path(tempfile.mkdtemp(prefix='corpus-builds-')))
            atexit.register(shutil.rmtree, _scratch[0], ignore_errors=True)
        directory = _scratch[0] / digest(key)
        directory.mkdir()
        _builds[key] = build(directory)
    return _builds[key]
