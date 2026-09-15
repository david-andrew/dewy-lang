"""Phase totals and process gauges remain distinct in benchmark records."""
from tools.measure_compiler import native_observations


def test_native_observations_accumulate_intervals_but_keep_gauges():
    result = native_observations('''dewy timing frontend 100 ns
ordinary diagnostic
error: dewy timing frontend 999 ns
dewy storage frontend allocated=1024 copied=10 live=100 peak=500
dewy timing frontend 200 ns
dewy storage frontend allocated=512 copied=20 live=50 peak=600
dewy timing backend 300 ns
dewy storage ignored allocated=-1 copied=0 live=0 peak=0
dewy storage ignored allocated=bad copied=0 live=0 peak=0
dewy storage ignored allocated=0 copied=0 live=0 wrong=0
''')
    assert result == {
        'reported_phase_nanoseconds': {'frontend': 300, 'backend': 300},
        'reported_phase_arena_bytes': {
            'frontend': {'allocated': 1536, 'copied': 30, 'live': 50, 'peak': 600},
        },
    }


def test_older_native_compilers_can_report_only_elapsed_time():
    assert native_observations('dewy timing frontend 100 ns\n') == {
        'reported_phase_nanoseconds': {'frontend': 100},
    }
