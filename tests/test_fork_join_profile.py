"""The performance gate cannot turn failed ratios or missing counters green."""
import importlib.util
import os
import subprocess
import sys

import pytest

from tests.support import compiler
from tests.test_fork_join_kernels import BENCH, ROOT


def profiler():
    path = ROOT / 'bench/parallel/profile.py'
    spec = importlib.util.spec_from_file_location('forkjoin_profile', path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_instruction_gate_and_scaling_are_independent():
    readings = {'serial': {'dewy': 100}, '1': {'dewy': 110, 'openmp': 99},
                '2': {'dewy': 100, 'openmp': 50}, '4': {'dewy': 100, 'openmp': 25}}
    assert not BENCH.gate_failures(readings, [1, 2, 4], instructions=True)
    failed = BENCH.gate_failures(readings, [1, 2, 4])
    assert len(failed) == 4
    assert any('scaling' in message for message in failed)
    readings['1']['dewy'] = 111
    assert 'T1/Tseq instructions=1.110' in BENCH.gate_failures(readings, [1], instructions=True)[0]


@pytest.mark.parametrize('text', ['', 'FJ_STATS 0 1 0 0 0 0 0 0 0 0 0', 'FJ_STATS 0 1'])
def test_bad_or_missing_counter_rows_fail(text):
    with pytest.raises(ValueError):
        profiler().parse_stats(text)


@pytest.mark.parametrize('kernel', ['fib', 'sum', 'mergesort', 'parallel_particles'])
def test_debug_runtime_ablation_preserves_results(compiler, tmp_path, kernel):
    profile = profiler()
    original = (ROOT / 'lib/std/fork_join.jo').read_bytes()
    expected = None
    for mode in ('normal', 'no-promotion'):
        directory = profile.stage(tmp_path, mode, counters=True, mode=mode, depth=4)
        binary = directory / kernel
        env = dict(os.environ, DEWY_CORE_LIB=str(directory / 'lib'), DEWY_EMIT_WORKERS='1')
        result = subprocess.run([compiler, 'build', directory / 'bench/parallel' / f'{kernel}.dewy',
                                 '--release', '-o', binary], env=env, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr
        for workers in (1, 2, 4):
            result = subprocess.run([binary, str(BENCH.SMALL[kernel])],
                                    env=dict(env, DEWY_THREADS=str(workers)),
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stderr
            checksum, _ = map(int, result.stdout.split())
            if expected is None:
                expected = checksum
            assert checksum == expected
            counts = profile.parse_stats(result.stderr)['total']
            if workers == 1:
                assert not any(counts.values())
            else:
                assert counts['forks'] > 0
                if mode == 'normal':
                    assert counts['promotions'] > 0
                else:
                    assert counts['clock_reads'] == counts['promotions'] == counts['steals'] == 0
                    if kernel == 'fib':
                        assert counts['forks'] == 4
                        assert counts['serial_frontiers'] == 1
    assert (ROOT / 'lib/std/fork_join.jo').read_bytes() == original


def test_runtime_hook_must_match_exactly_once():
    with pytest.raises(ValueError, match='hook changed'):
        profiler().replace_once('same same', 'same', 'different')


@pytest.mark.skipif(not hasattr(os, 'sched_getaffinity'), reason='Linux affinity counter')
def test_counter_pins_executable_and_restores_mask_after_failure():
    previous = os.sched_getaffinity(0)
    selected = [min(previous)]

    class FailingCounter:
        def run(self, command, env):
            assert command == ['/kernel', '32']
            assert os.sched_getaffinity(0) == set(selected)
            raise RuntimeError('counter failed')

    with pytest.raises(RuntimeError, match='counter failed'):
        BENCH.count_pinned(FailingCounter(), ['/kernel', '32'], {}, selected)
    assert os.sched_getaffinity(0) == previous


@pytest.mark.skipif(not hasattr(os, 'sched_getaffinity'), reason='Linux affinity counter')
def test_smt_selection_uses_distinct_cores_first(monkeypatch):
    monkeypatch.setattr(BENCH, 'physical_cpus', lambda: [0, 2])
    monkeypatch.setattr(BENCH.os, 'sched_getaffinity', lambda pid: {0, 1, 2, 3})
    assert BENCH.selected_cpus() == [0, 2]
    assert BENCH.selected_cpus(True) == [0, 2, 1, 3]
