"""Cycle reports must not silently interpret instructions or multiplexed counters."""
import pytest

from tools.compiler import speed, speed_cycles

pytestmark = pytest.mark.core_quick


def test_cycle_counter_requires_cycle_metric():
    assert speed.counter_result('{"cycles":123,"enabled_ns":5,"running_ns":5}', 'cycles') == 123
    for row in ('{"instructions":123,"enabled_ns":5,"running_ns":5}',
                '{"cycles":123,"enabled_ns":5,"running_ns":4}',
                '{"cycles":true,"enabled_ns":5,"running_ns":5}'):
        with pytest.raises(ValueError):
            speed.counter_result(row, 'cycles')


def test_cycle_run_pins_counter_and_selects_event(monkeypatch):
    from types import SimpleNamespace
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout='',
                               stderr='{"cycles":123,"enabled_ns":5,"running_ns":5}')

    monkeypatch.setattr(speed_cycles.subprocess, 'run', run)
    assert speed_cycles.run(SimpleNamespace(binary='counter'), ['compiler', 'build'], {}, 3, 'cycles') == 123
    assert calls == [['taskset', '-c', '3', 'counter', '--cycles', 'compiler', 'build']]


@pytest.mark.parametrize('args', [['--cycles'], ['--cycles', '--cpu', '3', '--runs', '14'],
                                  ['--cycles', '--cpu', '3', '--runs', '15', '--no-pin']])
def test_cycle_mode_rejects_uncontrolled_measurement(monkeypatch, args):
    monkeypatch.setattr(speed.os, 'sched_getaffinity', lambda _: {3}, raising=False)
    with pytest.raises(SystemExit) as result:
        speed.main(args, None)
    assert result.value.code == 2
