"""The compile-speed gate and the bench command: parsing and decisions, no compiles."""
import pytest

from tools.compiler import bench, speed

pytestmark = pytest.mark.core_quick


@pytest.mark.parametrize('stderr', ['', 'warning', '{}', '[]',
                                    '{"instructions": 3, "enabled_ns": 5, "running_ns": 4}',
                                    '{"instructions": 0, "enabled_ns": 5, "running_ns": 5}',
                                    '{"instructions": true, "enabled_ns": 5, "running_ns": 5}',
                                    '{"instructions": 3, "enabled_ns": 0, "running_ns": 0}'])
def test_speed_counter_rejects_unusable_measurement(stderr):
    with pytest.raises(ValueError):
        speed.counter_result(stderr)


def test_speed_counter_reads_final_line_after_diagnostics():
    assert speed.counter_result('compiler diagnostic\n'
                                '{"instructions": 123, "enabled_ns": 456, "running_ns": 456}\n') == 123


def test_speed_cachegrind_count():
    assert speed.cachegrind_result('==1== Collected : 1\n==1==\n==1== I refs:        1,039,842,123\n') == 1039842123
    assert speed.cachegrind_result('==1== I   refs:      7\n') == 7
    with pytest.raises(ValueError):
        speed.cachegrind_result('==1== ERROR SUMMARY: 0\n')


def test_speed_accept_lines():
    log = ('Inline more\n\nspeed: accept bigger inlining budget\n\n'
           'Other commit\nnot speed: accept this\nspeed: accept\n')
    assert speed.accepted(log) == ['bigger inlining budget']
    assert speed.accepted('Plain message\n') == []


def test_speed_stability_and_delta():
    assert speed.stable(1_000_000_000, 1_000_050_000)
    assert not speed.stable(1_000_000_000, 1_000_200_000)
    assert speed.delta(200, 203) == pytest.approx(1.5)


def test_speed_synthetic_program_is_deterministic():
    source = speed.generate_dewy(1000)
    assert source == speed.generate_dewy(1000)
    assert 21000 < source.count('\n') < 23000


def test_bench_selection():
    assert bench.selected(None) == list(bench.COUNTS)
    assert bench.selected('recursive') == ['recursive_list', 'recursive_tree']
    assert bench.selected('helpers,graph') == ['helpers', 'graph']
    assert bench.selected('nothing') == []
    for name in bench.COUNTS:
        assert (bench.BENCH / f'{name}.dewy').is_file()
        assert (bench.BENCH / f'{bench.C_SOURCE.get(name, name)}.c').is_file()


def test_speed_critical_path_reads_final_line():
    assert speed.critical_result('note\n{"own":5,"workers":[3,4],"critical":9,"total":12}\n') == (9, 12)
    with pytest.raises(ValueError):
        speed.critical_result('no count\n')
