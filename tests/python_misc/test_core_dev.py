"""The local driver must never silently validate a stale or failed compiler build."""
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import core

pytestmark = pytest.mark.core_quick


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


def test_core_driver_unchanged_launch_does_not_hash(checkout, monkeypatch):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    monkeypatch.setattr(core, 'digest', lambda path: pytest.fail(f'rehashed unchanged {path}'))
    assert core.toolchain(root=root, cache=cache) == first
    assert len(calls) == 1


@pytest.mark.parametrize('target', ['source', 'binary'])
def test_core_driver_detects_same_size_edit_with_restored_mtime(checkout, target):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    path = root / 'core/compiler/main.jo' if target == 'source' else first
    before = path.stat()
    path.write_bytes(b'!' * before.st_size)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert core.toolchain(root=root, cache=cache) != first
    assert calls[-1] == {'bootstrap': target == 'binary',
                         'seed': first if target == 'source' else None}


@pytest.mark.parametrize('target', ['source', 'binary'])
def test_core_driver_rechecks_touch_without_rebuilding(checkout, monkeypatch, target):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    path = root / 'core/compiler/main.jo' if target == 'source' else first
    before = path.stat()
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
    assert core.toolchain(root=root, cache=cache) == first
    monkeypatch.setattr(core, 'digest', lambda path: pytest.fail(f'rehashed unchanged {path}'))
    assert core.toolchain(root=root, cache=cache) == first
    assert len(calls) == 1


def test_core_driver_detects_added_and_deleted_sources(checkout):
    root, cache, calls = checkout
    first = core.toolchain(root=root, cache=cache)
    path = root / 'core/compiler/new_module.jo'
    path.write_text('new module')
    second = core.toolchain(root=root, cache=cache)
    assert second != first
    path.unlink()
    assert core.toolchain(root=root, cache=cache) != second
    assert len(calls) == 3


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


def test_core_driver_quick_command(monkeypatch, tmp_path):
    monkeypatch.setattr(core, 'toolchain', lambda **kwargs: tmp_path / 'dewy-core')
    received = {}

    def run(command, **options):
        received.update(command=command, **options)
        return 7

    monkeypatch.setattr(core.subprocess, 'call', run)
    assert core.main(['test', '--quick', '-k', 'dictionary']) == 7
    command = received['command']
    assert command[command.index('-m', 3)+1] == 'core_quick'
    assert command[-2:] == ['-k', 'dictionary']
    assert '--quick' not in command and 'xdist.plugin' not in command
    assert all(path in command for path in core.TESTS)


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
    assert core.main(['test', *arguments]) == 0
    command = received['command']
    if expected_workers is None:
        assert 'xdist.plugin' not in command
        assert '-n' not in command
    else:
        assert command[command.index('-n') + 1] == expected_workers
        assert 'xdist.plugin' in command
        assert 'tools.sloppy_core.pytest_parallel' in command
        assert '--dist=loadgroup' in command
    if arguments or cpus == 1:
        assert not probes
    else:
        assert len(probes) == 1 and probes[0][0] == command[0]
    assert all(path in command for path in core.TESTS)
    assert received['env']['DEWY_CORE_COMPILER'] == str(binary)
    assert received['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'


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
    shutil.copy2(Path(__file__).resolve().parents[2] / 'tools/dewy', launcher)
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


def test_core_checkout_launcher_stops_on_build_failure(tmp_path):
    tool_dir = tmp_path / 'tools'
    tool_dir.mkdir()
    launcher = tool_dir / 'dewy'
    shutil.copy2(Path(__file__).resolve().parents[2] / 'tools/dewy', launcher)
    (tool_dir / 'core.py').write_text('def toolchain():\n    raise RuntimeError("rebuild failed")\n')
    ran = subprocess.run([launcher, 'lsp'], cwd=tmp_path, capture_output=True,
                         text=True, timeout=10, check=False)
    assert ran.returncode == 1
    assert ran.stdout == ''
    assert ran.stderr == 'dewy development: rebuild failed\n'


@pytest.mark.parametrize(('ratios', 'expected'), [
    ([1.0] * 9, 'pass'),
    ([0.8] * 9, 'pass'),
    ([1.04] * 9, 'regression'),
    ([0.95, 1.08, 1.0, 1.05, 0.96, 1.06, 0.99, 1.04, 1.0], 'inconclusive'),
])
def test_core_performance_gate_distinguishes_noise(ratios, expected):
    from tools.sloppy_core.performance_gate import compare_samples
    # Host speed changes between pairs: compare each pair before aggregating.
    before = [float(2**i) for i in range(len(ratios))]
    after = [value * ratio for value, ratio in zip(before, ratios, strict=True)]
    result = compare_samples(before, after)
    assert result['status'] == expected


@pytest.mark.parametrize('bad', [[], [1.0] * 6, [0.0] * 9, [-1.0] * 9,
                               [float('nan')] * 9, [float('inf')] * 9, [1.0] * 10])
def test_core_performance_gate_rejects_missing_or_invalid_samples(bad):
    from tools.sloppy_core.performance_gate import compare_samples
    with pytest.raises(ValueError):
        compare_samples([1.0] * 9, bad)


def test_core_performance_gate_does_not_ratchet_or_claim_absolute_target():
    from tools.sloppy_core.performance_gate import assess
    compilation = {'workloads': {'throughput-default': {'cpu_seconds': {
        'reference': [1.0] * 9, 'previous': [1.05] * 9, 'candidate': [1.05] * 9}}}}
    runtime = {'workloads': {'kernel': {'samples': {
        **{f'{label}-{mode}': [{'kernel_ns': 100}] * 9
           for label in ('reference', 'previous', 'candidate') for mode in ('default', 'release')},
        'c': [{'kernel_ns': 100}] * 9}}}}
    result = assess(compilation, runtime, ['reference', 'previous'], 44005)
    assert result['comparisons']['compile/throughput-default/previous']['status'] == 'pass'
    assert result['comparisons']['compile/throughput-default/reference']['status'] == 'regression'
    assert not result['no_regression']
    assert not result['targets']['met_on_these_workloads']
    compilation['workloads']['throughput-default']['cpu_seconds']['candidate'] = [1.0] * 9
    result = assess(compilation, runtime, ['reference', 'previous'], 44005)
    assert result['no_regression']
    assert not result['targets']['met_on_these_workloads']
    for mode in ('default', 'release'):
        runtime['workloads']['kernel']['samples'][f'candidate-{mode}'] = [{'kernel_ns': 130}] * 9
    assert not assess(compilation, runtime, ['reference', 'previous'], 44005)['no_regression']
    runtime['workloads']['kernel']['binary_sha256'] = {
        f'{label}-{mode}': 'same-artifact' for label in ('reference', 'previous', 'candidate')
        for mode in ('default', 'release')}
    assert assess(compilation, runtime, ['reference', 'previous'], 44005)['no_regression']
    workload = runtime['workloads']['kernel']
    workload['binary_sha256'] = {}
    workload['artifact_identity'] = {
        f'{label}-{mode}': {'masked_sha256': 'same-code', 'bundle_path_bytes': 80, 'occurrences': 9}
        for label in ('reference', 'previous', 'candidate') for mode in ('default', 'release')}
    assert assess(compilation, runtime, ['reference', 'previous'], 44005)['no_regression']
    candidate = workload['artifact_identity']['candidate-default']
    for field, value in [('masked_sha256', 'different-code'), ('bundle_path_bytes', 81), ('occurrences', 8)]:
        saved = candidate[field]
        candidate[field] = value
        assert not assess(compilation, runtime, ['reference', 'previous'], 44005)['no_regression']
        candidate[field] = saved


@pytest.mark.parametrize('change', ['binary', 'modified', 'missing', 'extra'])
def test_core_performance_gate_rejects_changed_toolchain(tmp_path, change):
    import hashlib

    from tools.sloppy_core.performance_gate import toolchain_identity
    binary = tmp_path / 'bin/dewy-core'
    binary.parent.mkdir()
    binary.write_bytes(b'compiler')
    sources = {}
    for name in ('compiler/main.jo', 'lib/rt.jo'):
        path = tmp_path / name
        path.parent.mkdir()
        path.write_bytes(b'source')
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / 'build.json').write_text(json.dumps({
        'core_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'sources_sha256': sources}))
    toolchain_identity(binary)
    if change == 'binary':
        binary.write_bytes(b'changed')
    elif change == 'modified':
        (tmp_path / 'lib/rt.jo').write_bytes(b'changed')
    elif change == 'missing':
        (tmp_path / 'lib/rt.jo').unlink()
    else:
        (tmp_path / 'lib/extra.jo').write_bytes(b'extra')
    with pytest.raises(ValueError):
        toolchain_identity(binary)


def test_core_performance_artifact_masks_only_bundle_path(tmp_path):
    from tools.sloppy_core.benchmark_apps import artifact_identity

    binaries = []
    for name in ('first', 'other'):
        compiler = tmp_path / name / 'bin/core'
        artifact = tmp_path / name / 'program'
        artifact.parent.mkdir()
        prefix = str(compiler.parent.parent).encode()
        artifact.write_bytes(b'code\0' + prefix + b'/lib/rt.jo:42\0data')
        binaries.append((artifact, compiler))
    before, after = [artifact_identity(*pair) for pair in binaries]
    assert before['binary_sha256'] != after['binary_sha256']
    assert before['masked_sha256'] == after['masked_sha256']
    assert before['occurrences'] == after['occurrences'] == 1
    artifact, compiler = binaries[1]
    artifact.write_bytes(artifact.read_bytes().replace(b'data', b'else'))
    assert artifact_identity(artifact, compiler)['masked_sha256'] != before['masked_sha256']
    artifact.write_bytes(artifact.read_bytes().replace(b'code', b'longer code'))
    assert artifact_identity(artifact, compiler)['masked_sha256'] != before['masked_sha256']


@pytest.mark.parametrize('count', [2, 3, 7])
def test_core_benchmark_balances_variant_positions(count):
    from collections import Counter

    from tools.sloppy_core.benchmark_compile import sample_order
    labels = [str(i) for i in range(count)]
    orders = [sample_order(labels, sample) for sample in range(2 * count)]
    assert all(sorted(order) == labels for order in orders)
    for position in range(count):
        assert Counter(order[position] for order in orders) == Counter({label: 2 for label in labels})


def test_core_benchmark_reuses_only_equivalent_artifacts():
    from tools.sloppy_core.benchmark_apps import artifact_representatives
    base = {'binary_sha256': 'raw', 'masked_sha256': 'code', 'bundle_path_bytes': 80, 'occurrences': 3}
    artifacts = {'reference': base, 'same_raw': {**base, 'binary_sha256': 'raw'},
                 'same_code': {**base, 'binary_sha256': 'different'},
                 'changed_code': {**base, 'binary_sha256': 'other', 'masked_sha256': 'new'},
                 'changed_width': {**base, 'binary_sha256': 'other2', 'bundle_path_bytes': 81},
                 'missing_identity': {}}
    assert artifact_representatives(artifacts) == {'same_raw': 'reference', 'same_code': 'reference'}


@pytest.mark.parametrize('bad_duplicate', [False, True])
def test_core_benchmark_reuse_still_checks_each_binary(tmp_path, monkeypatch, bad_duplicate):
    from collections import Counter
    from copy import deepcopy

    from tools.sloppy_core import benchmark_apps as apps

    compilers = {}
    for label in ('first', 'other'):
        compiler = tmp_path / label / 'bin/core'
        compiler.parent.mkdir(parents=True)
        compiler.write_bytes(b'compiler')
        compilers[label] = compiler

    def fake_run(command, _env):
        if '--version' in command:
            return 'test C compiler', 0.0
        binary = Path(command[command.index('-o') + 1])
        if 'build' in command:
            prefix = str(Path(command[0]).parent.parent).encode()
            binary.write_bytes(b'code\0' + prefix + b'/lib/rt.jo\0data')
        else:
            binary.write_bytes(b'C code')
        return '', 0.0

    executed = Counter()

    def fake_execute(command, count, _env):
        label = Path(command[0]).name.removeprefix('arrays-')
        executed[label, count] += 1
        checksum = count
        if bad_duplicate and label == 'other' and count == 99:
            checksum += 1
        return checksum, {'kernel_ns': 100, 'wall_seconds': 0.001}

    monkeypatch.setattr(apps, 'run', fake_run)
    monkeypatch.setattr(apps, 'execute', fake_execute)
    completed = []

    def checkpoint(report):
        completed.append(deepcopy(report))

    if bad_duplicate:
        with pytest.raises(RuntimeError, match='checksum|expected'):
            apps.measure(compilers, ['arrays'], 7, 'cc', count=99, reuse_identical_artifacts=True,
                         on_progress=checkpoint)
        assert executed['other', 99] == 1
        assert completed == []
        return
    report = apps.measure(compilers, ['arrays'], 7, 'cc', count=99, reuse_identical_artifacts=True,
                          on_progress=checkpoint)
    assert len(completed) == 1
    assert completed[0]['workloads'] == report['workloads']
    workload = report['workloads']['arrays']
    assert workload['timing_reused_from'] == {'other': 'first'}
    assert workload['samples']['other'] == workload['samples']['first']
    for label in ('first', 'other', 'c'):
        for count in (0, 1, 17, 1000):
            assert executed[label, count] == 1
    assert executed['first', 99] == executed['c', 99] == 8
    assert executed['other', 99] == 1


def test_core_performance_checkpoint_preserves_previous_report_on_failure(tmp_path):
    from tools.sloppy_core.performance_gate import save_report

    path = tmp_path / 'gate.json'
    partial = {'status': 'incomplete', 'compilation': {'workloads': {'finished': {}}}}
    save_report(path, partial)
    with pytest.raises(TypeError):
        save_report(path, {'not_serializable': object()})
    assert json.loads(path.read_text()) == partial
    assert sorted(p.name for p in tmp_path.iterdir()) == ['gate.json']
    complete = {**partial, 'status': 'complete', 'assessment': {'no_regression': False}}
    save_report(path, complete)
    assert json.loads(path.read_text()) == complete


@pytest.mark.skipif(not Path('/proc/cpuinfo').exists(), reason='Linux stage benchmark')
@pytest.mark.parametrize('failure', ['runtime', 'identity', None])
def test_core_performance_checkpoint_never_accepts_an_incomplete_gate(tmp_path, monkeypatch, failure):
    from tools.sloppy_core import performance_gate as gate

    pinned = json.loads(gate.REFERENCE.read_text())
    identity = {key: pinned[key] for key in ('compiler_sources_sha256', 'library_sha256')}
    calls = 0

    def toolchain_identity(_binary):
        nonlocal calls
        calls += 1
        return {**identity, 'changed': True} if failure == 'identity' and calls > 3 else identity

    def compilation(*_args, on_progress):
        result = {'workloads': {'finished': {'cpu_seconds': [1]}}}
        on_progress(result)
        return result

    def runtime(*_args, on_progress, **_kwargs):
        result = {'workloads': {'finished': {'samples': [1]}}}
        on_progress(result)
        if failure == 'runtime':
            raise RuntimeError('interrupted runtime')
        return result

    monkeypatch.setattr(gate, 'ROOT', tmp_path)
    monkeypatch.setattr(gate, 'toolchain_identity', toolchain_identity)
    monkeypatch.setattr(gate.benchmark_compile, 'measure', compilation)
    monkeypatch.setattr(gate.benchmark_apps, 'measure', runtime)
    monkeypatch.setattr(gate, 'assess', lambda *_args: {'no_regression': True})
    path = tmp_path / 'gate.json'
    compiler = tmp_path / 'bundle/bin/core'
    workloads = gate.benchmark_compile.WORKLOADS.copy()

    def measure():
        return gate.measure(compiler, compiler, compiler, 7,
                            on_progress=lambda report: gate.save_report(path, report))

    if failure:
        with pytest.raises((RuntimeError, ValueError), match='interrupted|changed'):
            measure()
    else:
        result = measure()
        assert result['status'] == 'complete'
        assert result['assessment']['no_regression']
    partial = json.loads(path.read_text())
    assert partial['status'] == 'incomplete'
    assert 'assessment' not in partial
    assert 'finished' in partial['compilation']['workloads']
    assert 'finished' in partial['runtime']['workloads']
    assert gate.benchmark_compile.WORKLOADS == workloads
