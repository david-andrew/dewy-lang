"""bench --baseline's decision: more than the limit in instructions, or another checksum, fails."""
from tools.compiler import bench


def test_bench_compare_limit():
    assert bench.compare('k (default)', [1000, 1030], ['7', '7'], 3.0) == (3.0, [])
    change, failures = bench.compare('k (release)', [1000, 1031], ['7', '7'], 3.0)
    assert change == 3.1 and failures == ['k (release) needs +3.10% instructions (limit 3.0%)']
    assert bench.compare('k (default)', [1000, 900], ['7', '7'], 3.0) == (-10.0, [])


def test_bench_compare_checksum():
    _, failures = bench.compare('k (default)', [1000, 1000], ['7', '8'], 3.0)
    assert failures == ['k (default) prints checksum 8, base 7']
