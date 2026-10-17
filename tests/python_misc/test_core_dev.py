"""The local driver must never silently validate a stale or failed compiler build."""
import json

import pytest

from tools import core


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    for name in ('compiler/main.jo', 'lib/core/rt.jo', 'stage0/main.c', 'bootstrap/frontend.jo',
                 'LICENSE', 'NOTICE', 'UPSTREAM.json'):
        path = root / 'core' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    builder = root / 'tools/sloppy_core/build.py'
    builder.parent.mkdir(parents=True)
    builder.write_text('builder')
    calls = []

    def build(output, **options):
        calls.append(options)
        binary = output / 'bin/dewy-core'
        binary.parent.mkdir(parents=True)
        binary.write_text(f'compiler generation {len(calls)}')
        return binary

    monkeypatch.setattr(core, 'build', build)
    return root, tmp_path / 'cache', calls


@pytest.mark.parametrize('changed', ['core/compiler/main.jo', 'core/lib/core/rt.jo',
                                   'core/stage0/main.c', 'core/bootstrap/frontend.jo',
                                   'tools/sloppy_core/build.py'])
def test_core_driver_rebuilds_changed_inputs(checkout, changed):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    assert calls == [{'bootstrap': True, 'seed': None}]
    assert core.toolchain(root=root, cache=cache) == first
    assert len(calls) == 1
    (root / 'README.md').write_text('Documentation does not change the toolchain.')
    assert core.toolchain(root=root, cache=cache) == first
    (root / changed).write_text('changed input')
    second = core.toolchain(root=root, cache=cache)
    assert second != first and first.exists()
    assert calls[-1] == {'bootstrap': False, 'seed': first}
    assert core.toolchain(root=root, cache=cache) == second
    assert len(calls) == 2


@pytest.mark.parametrize('damage', ['missing', 'modified'])
def test_core_driver_rejects_damaged_seed(checkout, damage):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    if damage == 'missing':
        first.unlink()
    else:
        first.write_text('not the compiler we built')
    assert core.toolchain(root=root, cache=cache) != first
    assert calls[-1] == {'bootstrap': True, 'seed': None}


def test_core_driver_forced_bootstrap(checkout):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    assert core.toolchain(root=root, cache=cache, bootstrap=True) != first
    assert calls[-1] == {'bootstrap': True, 'seed': None}


def test_core_driver_keeps_previous_state_after_failure(checkout, monkeypatch):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    state = (cache / 'current.json').read_bytes()
    (root / 'core/compiler/main.jo').write_text('new source')
    builder = core.build

    def fail(*args, **kwargs):
        raise RuntimeError('compile failed')

    monkeypatch.setattr(core, 'build', fail)
    with pytest.raises(RuntimeError, match='compile failed'):
        core.toolchain(root=root, cache=cache)
    assert (cache / 'current.json').read_bytes() == state
    monkeypatch.setattr(core, 'build', builder)
    assert core.toolchain(root=root, cache=cache) != first
    assert calls[-1] == {'bootstrap': False, 'seed': first}


def test_core_driver_rejects_source_edit_during_build(checkout, monkeypatch):
    root, cache, _ = checkout
    builder = core.build

    def editing_build(*args, **kwargs):
        result = builder(*args, **kwargs)
        (root / 'core/compiler/main.jo').write_text('concurrent edit')
        return result

    monkeypatch.setattr(core, 'build', editing_build)
    with pytest.raises(RuntimeError, match='changed during the build'):
        core.toolchain(root=root, cache=cache)
    assert not (cache / 'current.json').exists()


def test_core_driver_test_command(monkeypatch, tmp_path):
    binary = tmp_path / 'dewy-core'
    monkeypatch.setattr(core, 'toolchain', lambda **kwargs: binary)
    monkeypatch.setenv('DEWY_CORE_COMPILER', '/stale/compiler')
    monkeypatch.setenv('DEWY_CORE_FRONTEND', 'legacy')
    monkeypatch.setenv('SLOPPY_LIB', '/stale/library')
    received = {}

    def run(command, **options):
        received.update(command=command, **options)
        return 7

    monkeypatch.setattr(core.subprocess, 'call', run)
    assert core.main(['test', '-k', 'record']) == 7
    assert received['command'][-2:] == ['-k', 'record']
    assert '--maxfail=1' in received['command']
    assert all(path in received['command'] for path in core.TESTS)
    assert received['env']['DEWY_CORE_COMPILER'] == str(binary)
    assert received['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
    assert 'DEWY_CORE_FRONTEND' not in received['env']
    assert 'SLOPPY_LIB' not in received['env']


def test_core_driver_rejects_cache_path_outside_owned_directory(tmp_path):
    binary = tmp_path / 'unrelated'
    binary.write_text('not a cache entry')
    cache = tmp_path / 'cache'
    cache.mkdir()
    (cache / 'current.json').write_text(json.dumps({
        'binary': '../unrelated', 'binary_sha256': core.digest(binary),
    }))
    assert core.cached_state(cache) == ({}, None)
