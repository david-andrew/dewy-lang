"""The local driver must never silently validate a stale or failed compiler build."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import core


@pytest.mark.core_quick
@pytest.mark.parametrize('phase,status,code,output,expected', [
    ('run', 'complete', 0, b'answer', 'pass'),
    ('run', 'complete', 0, b'wrong', 'mismatch'),
    ('build', 'complete', 1, b'answer', 'execution-error'),
    ('run', 'complete', -11, b'answer', 'execution-error'),
    ('run', 'timeout', -9, b'answer', 'incomplete'),
    ('run', 'output-limit', 0, b'answer', 'incomplete'),
])
def test_fuzz_outcome_requires_success_in_every_mode(phase, status, code, output, expected):
    from tools.compiler.fuzz import outcome

    reference = dict(phase='run', status='complete', returncode=0, stdout=b'answer')
    candidate = dict(phase=phase, status=status, returncode=code, stdout=output)
    assert outcome({'default': reference, 'release': candidate}) == expected
    if phase == 'build' or status != 'complete' or code:
        assert outcome({'default': candidate, 'release': candidate}) != 'pass'


@pytest.mark.core_quick
def test_fuzz_no_results_cannot_pass():
    from tools.compiler.fuzz import outcome

    assert outcome({}) == 'incomplete'


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    for name in ('compiler/main.jo', 'lib/core/rt.jo', 'stage0/main.c', 'bootstrap/frontend.jo', 'LICENSE'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    builder = root / 'tools/compiler/build.py'
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


@pytest.mark.core_quick
@pytest.mark.parametrize('changed', ['compiler/main.jo', 'lib/core/rt.jo',
                                   'stage0/main.c', 'bootstrap/frontend.jo',
                                   'tools/compiler/build.py'])
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


@pytest.mark.core_quick
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


@pytest.mark.core_quick
def test_core_driver_unchanged_launch_does_not_hash(checkout, monkeypatch):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    monkeypatch.setattr(core, 'digest', lambda path: pytest.fail(f'rehashed unchanged {path}'))
    assert core.toolchain(root=root, cache=cache) == first
    assert len(calls) == 1


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['source', 'binary'])
def test_core_driver_detects_same_size_edit_with_restored_mtime(checkout, target):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    path = root / 'compiler/main.jo' if target == 'source' else first
    before = path.stat()
    path.write_bytes(b'!' * before.st_size)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert core.toolchain(root=root, cache=cache) != first
    assert calls[-1] == {'bootstrap': target == 'binary',
                         'seed': first if target == 'source' else None}


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['source', 'binary'])
def test_core_driver_rechecks_touch_without_rebuilding(checkout, monkeypatch, target):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    path = root / 'compiler/main.jo' if target == 'source' else first
    before = path.stat()
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
    assert core.toolchain(root=root, cache=cache) == first
    monkeypatch.setattr(core, 'digest', lambda path: pytest.fail(f'rehashed unchanged {path}'))
    assert core.toolchain(root=root, cache=cache) == first
    assert len(calls) == 1


@pytest.mark.core_quick
def test_core_driver_detects_added_and_deleted_sources(checkout):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    path = root / 'compiler/new_module.jo'
    path.write_text('new module')
    second = core.toolchain(root=root, cache=cache)
    assert second != first
    path.unlink()
    assert core.toolchain(root=root, cache=cache) != second
    assert len(calls) == 3


@pytest.mark.core_quick
def test_core_driver_upgrades_existing_cache_without_rebuilding(checkout, monkeypatch):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    path = cache / 'current.json'
    state = json.loads(path.read_text())
    del state['source_stamp'], state['binary_stamp']
    path.write_text(json.dumps(state))
    assert core.toolchain(root=root, cache=cache) == first
    monkeypatch.setattr(core, 'digest', lambda path: pytest.fail(f'rehashed unchanged {path}'))
    assert core.toolchain(root=root, cache=cache) == first
    assert len(calls) == 1


@pytest.mark.core_quick
def test_core_driver_forced_bootstrap(checkout):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    assert core.toolchain(root=root, cache=cache, bootstrap=True) != first
    assert calls[-1] == {'bootstrap': True, 'seed': None}


@pytest.mark.core_quick
def test_core_driver_keeps_previous_state_after_failure(checkout, monkeypatch):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    state = (cache / 'current.json').read_bytes()
    (root / 'compiler/main.jo').write_text('new source')
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


@pytest.mark.core_quick
def test_core_driver_rejects_source_edit_during_build(checkout, monkeypatch):
    root, cache, _ = checkout
    builder = core.build

    def editing_build(*args, **kwargs):
        result = builder(*args, **kwargs)
        (root / 'compiler/main.jo').write_text('concurrent edit')
        return result

    monkeypatch.setattr(core, 'build', editing_build)
    with pytest.raises(RuntimeError, match='changed during the build'):
        core.toolchain(root=root, cache=cache)
    assert not (cache / 'current.json').exists()


def stub_stages(monkeypatch):
    """Record the golden-case and ladder stages instead of running them."""
    from tools import cases, ladder
    calls = []
    # (the interpreter probe runs subprocesses some of these tests intercept)
    monkeypatch.setattr(core, 'pytest_python', lambda: Path(core.sys.executable))
    monkeypatch.setattr(cases, 'run', lambda binary, chosen, **options: calls.append(
        ('cases', len(chosen), options['workers'])) or 0)
    monkeypatch.setattr(ladder, 'run', lambda binary, **options: calls.append(
        ('ladder', options['keyword'], options['workers'])) or 0)
    return calls


def test_core_driver_test_command(monkeypatch, tmp_path):
    binary = tmp_path / 'dewy-core'
    monkeypatch.setattr(core, 'toolchain', lambda **kwargs: binary)
    monkeypatch.setenv('DEWY_CORE_COMPILER', '/stale/compiler')
    monkeypatch.setenv('DEWY_CORE_LIB', '/stale/library')
    received = {}

    def run(command, **options):
        received.update(command=command, **options)
        return 7

    monkeypatch.setattr(core.subprocess, 'call', run)
    stages = stub_stages(monkeypatch)
    assert core.main(['test', '-k', 'snapshot']) == 7
    # -k selects golden cases too; no ladder program matches 'snapshot'.
    assert [stage[0] for stage in stages] == ['cases'] and stages[0][1] > 0
    assert received['command'][-2:] == ['-k', 'snapshot']
    assert '--maxfail=1' in received['command']
    assert all(path in received['command'] for path in core.TESTS)
    assert received['env']['DEWY_CORE_COMPILER'] == str(binary)
    assert received['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
    assert 'DEWY_CORE_LIB' not in received['env']


def test_core_driver_quick_command(monkeypatch, tmp_path):
    monkeypatch.setattr(core, 'toolchain', lambda **kwargs: tmp_path / 'dewy-core')
    received = {}

    def run(command, **options):
        received.update(command=command, **options)
        return 7

    monkeypatch.setattr(core.subprocess, 'call', run)
    stages = stub_stages(monkeypatch)
    assert core.main(['test', '--quick', '-k', 'dictionary']) == 7
    assert [stage[0] for stage in stages] == ['cases'], 'the quick suite skips the ladder'
    command = received['command']
    assert command[command.index('-m', 3)+1] == 'core_quick'
    assert command[-2:] == ['-k', 'dictionary']
    assert '--quick' not in command and 'xdist.plugin' not in command
    assert all(path in command for path in core.TESTS)


@pytest.mark.core_quick
def test_core_driver_quick_rejects_marker_override(monkeypatch):
    monkeypatch.setattr(core, 'toolchain', lambda **kwargs: pytest.fail('validation must precede building'))
    with pytest.raises(SystemExit) as exited:
        core.main(['test', '--quick', '-m', 'anything'])
    assert exited.value.code == 2


@pytest.mark.parametrize('arguments, cpus, available, expected_workers', [
    ([], 16, True, '4'),
    ([], 2, True, '2'),
    ([], 1, True, None),
    ([], 16, False, None),
    (['-k', 'json'], 16, True, None),
    (['-n', '0'], 16, True, '0'),
    (['-n', '2', '-k', 'json'], 16, True, '2'),
])
def test_core_driver_worker_selection(monkeypatch, tmp_path, arguments, cpus, available, expected_workers):
    binary = tmp_path / 'dewy-core'
    monkeypatch.setattr(core, 'toolchain', lambda **kwargs: binary)
    monkeypatch.setattr(core.os, 'process_cpu_count', lambda: cpus, raising=False)
    probes = []
    received = {}

    def probe(command, **options):
        probes.append(command)
        return SimpleNamespace(returncode=0 if available else 1)

    def run(command, **options):
        received.update(command=command, **options)
        return 0

    monkeypatch.setattr(core.subprocess, 'run', probe)
    monkeypatch.setattr(core.subprocess, 'call', run)
    stages = stub_stages(monkeypatch)
    assert core.main(['test', *arguments]) == 0
    assert stages[0][2] == (int(expected_workers) or 1 if '-n' in arguments else min(4, cpus))
    assert [stage[0] for stage in stages] == ['cases', 'ladder']  # -k json matches 16_json_roundtrip
    command = received['command']
    if expected_workers is None:
        assert 'xdist.plugin' not in command
        assert '-n' not in command
    else:
        assert command[command.index('-n') + 1] == expected_workers
        assert 'xdist.plugin' in command
        assert 'tools.compiler.pytest_parallel' in command
        assert '--dist=loadgroup' in command
    if arguments or cpus == 1:
        assert not probes
    else:
        assert len(probes) == 1 and probes[0][0] == command[0]
    assert all(path in command for path in core.TESTS)
    assert received['env']['DEWY_CORE_COMPILER'] == str(binary)
    assert received['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'


@pytest.mark.core_quick
def test_core_driver_rejects_cache_path_outside_owned_directory(tmp_path):
    binary = tmp_path / 'unrelated'
    binary.write_text('not a cache entry')
    cache = tmp_path / 'cache'
    cache.mkdir()
    (cache / 'current.json').write_text(json.dumps({
        'binary': '../unrelated', 'binary_sha256': core.digest(binary),
    }))
    assert core.cached_state(cache) == ({}, None)


@pytest.mark.parametrize('arguments, linked', [
    (['lsp'], False),
    (['program with spaces.dewy', 'one', 'second value'], False),
    (['--version'], True),
])
def test_core_checkout_launcher(tmp_path, arguments, linked):
    checkout = tmp_path / 'checkout with spaces'
    tool_dir = checkout / 'tools'
    tool_dir.mkdir(parents=True)
    launcher = tool_dir / 'dewy'
    shutil.copy2(Path(__file__).resolve().parents[1] / 'tools/dewy', launcher)
    (tool_dir / 'core.py').write_text(
        'import sys\nfrom pathlib import Path\n'
        'def toolchain():\n'
        '    print("building current compiler", file=sys.stderr)\n'
        '    return Path(__file__).resolve().parents[1] / "native compiler"\n')
    native = checkout / 'native compiler'
    native.write_text('#!/usr/bin/env python3\nimport json, os, sys\n'
                      'print(json.dumps([sys.argv[1:], os.getcwd(), sys.stdin.read(), os.getpid()]))\n')
    native.chmod(0o755)
    caller = tmp_path / 'another project'
    caller.mkdir()
    if linked:
        entry = caller / 'dewy'
        entry.symlink_to(launcher)
    else:
        entry = launcher
    with subprocess.Popen([entry, *arguments], cwd=caller, stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        output, errors = process.communicate('editor protocol bytes', timeout=10)
        assert process.returncode == 0, errors
        assert json.loads(output) == [arguments, str(caller), 'editor protocol bytes', process.pid]
        assert errors == 'building current compiler\n'


@pytest.mark.core_quick
def test_core_checkout_launcher_stops_on_build_failure(tmp_path):
    tool_dir = tmp_path / 'tools'
    tool_dir.mkdir()
    launcher = tool_dir / 'dewy'
    shutil.copy2(Path(__file__).resolve().parents[1] / 'tools/dewy', launcher)
    (tool_dir / 'core.py').write_text('def toolchain():\n    raise RuntimeError("rebuild failed")\n')
    ran = subprocess.run([launcher, 'lsp'], cwd=tmp_path, capture_output=True,
                         text=True, timeout=10, check=False)
    assert ran.returncode == 1
    assert ran.stdout == ''
    assert ran.stderr == 'dewy development: rebuild failed\n'
