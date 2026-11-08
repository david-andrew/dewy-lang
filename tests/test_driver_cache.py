"""The persistent driver cache never reuses a build whose inputs changed, publishes atomically
under concurrent workers and stays within its size cap."""
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor

import pytest

from tests import driver_cache
from tests.driver_cache import build_driver, evict, identity
from tests.support import compiler  # noqa: F401 (fixture)


def graph(value):
    # (a leaf module, as a twin test supplies one, and the driver that calls it)
    return {'leaf.jo': f'answer = () -> int: {value}\n',
            'driver.jo': "use 'leaf.jo'\nmain = ():\n    print(answer())\n"}


def entries(cache):
    return [e for shard in cache.iterdir() if shard.name not in ('stage', 'evict.lock') and shard.is_dir()
            for e in shard.iterdir() if e.is_dir()]


def output(binary):
    return subprocess.run([binary], capture_output=True, text=True, timeout=30).stdout.strip()


def test_changed_leaf_rebuilds(compiler, tmp_path):
    cache = tmp_path / 'cache'
    first = build_driver(compiler, graph(1), cache=cache)
    assert output(first) == '1'
    stamp = first.stat().st_mtime_ns
    # an unchanged graph is a hit: the same file, not rebuilt
    again = build_driver(compiler, graph(1), cache=cache)
    assert again == first and again.stat().st_mtime_ns == stamp
    # an edited leaf is a different key, built fresh, and the old entry stays valid
    edited = build_driver(compiler, graph(2), cache=cache)
    assert edited != first and output(edited) == '2'
    assert output(first) == '1'
    assert len(entries(cache)) == 2


def test_every_input_is_in_the_key(tmp_path, monkeypatch):
    fake = tmp_path / 'bin' / 'dewy-core'
    fake.parent.mkdir()
    fake.write_bytes(b'one')
    library = tmp_path / 'lib'
    library.mkdir()
    (library / 'rt.jo').write_text('x = 1\n')
    monkeypatch.setenv('DEWY_CORE_LIB', str(library))
    monkeypatch.delenv('DEWY_EMIT_WORKERS', raising=False)   # (CI sets it; the key must see a change)
    modules = graph(1)
    base = identity(fake, modules)
    assert identity(fake, dict(modules)) == base
    assert identity(fake, modules, release=True) != base
    assert identity(fake, modules, flags=('--fast',)) != base
    assert identity(fake, graph(2)) != base
    assert identity(fake, {**modules, 'extra.jo': ''}) != base
    (library / 'rt.jo').write_text('x = 2\n')
    assert identity(fake, modules) != base
    (library / 'rt.jo').write_text('x = 1\n')
    assert identity(fake, modules) == base
    fake.write_bytes(b'two')
    assert identity(fake, modules) != base
    fake.write_bytes(b'one')
    monkeypatch.setenv('DEWY_EMIT_WORKERS', '1')
    assert identity(fake, modules) != base


def concurrent_build(arguments):
    compiler, cache, value = arguments
    return str(build_driver(compiler, graph(value), cache=cache))


def test_concurrent_workers_share_one_build(compiler, tmp_path):
    cache = tmp_path / 'cache'
    with ProcessPoolExecutor(4) as pool:
        paths = list(pool.map(concurrent_build, [(compiler, cache, 7)] * 6 + [(compiler, cache, 8)] * 2))
    assert set(paths[:6]) == {paths[0]} and paths[0] != paths[6]
    assert output(paths[0]) == '7' and output(paths[6]) == '8'
    assert len(entries(cache)) == 2
    assert list((cache / 'stage').iterdir()) == []  # (no half-built stage left behind)


def test_least_recently_used_entries_are_evicted(compiler, tmp_path):
    cache = tmp_path / 'cache'
    binaries = [build_driver(compiler, graph(n), cache=cache) for n in (11, 12, 13)]
    size = binaries[0].stat().st_size
    now = time.time()
    # use order: 12 (oldest), 13, 11 (newest)
    for binary, age in ((binaries[1], 300), (binaries[2], 200), (binaries[0], 100)):
        os.utime(binary.parent, (now - age, now - age))
    evict(cache, cap=size * 2 + size // 2, protect=0)
    assert [b.exists() for b in binaries] == [True, False, True]
    # an entry used within the protection window is never removed, even over the cap
    os.utime(binaries[0].parent)
    evict(cache, cap=1, protect=3600)
    assert binaries[0].exists()
    evict(cache, cap=1, protect=0)
    assert not any(b.exists() for b in binaries)


def test_evict_tolerates_a_stage_removed_meanwhile(tmp_path, monkeypatch):
    """A worker's build can finish and remove its stage between eviction listing and stat-ing it."""
    from pathlib import Path
    (tmp_path / 'stage' / 'build-gone').mkdir(parents=True)
    real = Path.stat

    def vanishing(self, *args, **kwargs):
        if self.name == 'build-gone':
            raise FileNotFoundError(self)
        return real(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', vanishing)
    evict(tmp_path)
