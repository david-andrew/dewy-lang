"""Hard flagship throughput floors and demand-aware source-cost limits in tools/compiler/speed.py."""
from tools.compiler import speed


def _report(root_lines: int, lib_lines: int) -> str:
    return (
        'instructions: 1000; shared 10: check 10 optimize 1; root 10: load 5 optimize 1\n'
        'nodes: root 8, library 0, shared 0\n'
        f'lines: root {root_lines}, library {lib_lines}, instance 0; 0 instances; library parsed 1, bodies reached 0 of 0\n'
    )


def test_source_cost_limit_allows_feature_headroom_when_flagships_stay_flat():
    base = {'flagship 95_kv_store': 100_000, 'flagship 96_ct_crypto': 100_000}
    flat = {'flagship 95_kv_store': 100_400, 'flagship 96_ct_crypto': 100_400}
    regressed_one = {'flagship 95_kv_store': 100_800, 'flagship 96_ct_crypto': 99_500}
    assert speed.source_cost_limit(1.0, flat, base) == speed.SOURCE_FEATURE_LIMIT == 1.5
    assert speed.source_cost_limit(1.0, regressed_one, base) == speed.SOURCE_LIMIT == 1.0
    assert speed.source_cost_limit(2.0, regressed_one, base) == 2.0
    assert speed.source_cost_limit(1.0, {}, {}) == speed.SOURCE_LIMIT


def test_yardstick_enforces_250k_aggregate_and_200k_per_flagship_floors(monkeypatch):
    fake_panel = [
        ('hello', 'hello.dewy', []),
        ('flagship 95_kv_store', 'f1.dewy', []),
        ('flagship 96_ct_crypto', 'f2.dewy', []),
    ]
    monkeypatch.setattr(speed, 'panel', lambda release: fake_panel)
    monkeypatch.setattr(speed, 'time_run', lambda tc, src: _report(1000, 4000))
    tc = speed.Toolchain('candidate', None, None)

    # 5000 lines at IPS=6.3e9: 250k lines/s -> 126_000_000 inst; 200k lines/s -> 157_500_000 inst.
    passing = {'hello': 26_000_000, 'flagship 95_kv_store': 120_000_000, 'flagship 96_ct_crypto': 120_000_000}
    assert speed.yardstick(tc, passing) == []

    # One flagship below 200k even though aggregate stays above 250k.
    one_slow = {'hello': 26_000_000, 'flagship 95_kv_store': 160_000_000, 'flagship 96_ct_crypto': 80_000_000}
    got = speed.yardstick(tc, one_slow)
    assert len(got) == 1 and 'flagship 95_kv_store' in got[0] and '200,000' in got[0]

    # Both above 200k individually (225k each), but aggregate below 250k.
    agg_slow = {'hello': 26_000_000, 'flagship 95_kv_store': 140_000_000, 'flagship 96_ct_crypto': 140_000_000}
    got = speed.yardstick(tc, agg_slow)
    assert len(got) == 1 and 'flagships (sum)' in got[0] and '250,000' in got[0]
