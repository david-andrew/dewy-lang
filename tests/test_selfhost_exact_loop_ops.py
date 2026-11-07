"""Exact map helpers (tagged sources and stores, element magnitudes, fresh broadcast arrays, element declarations) agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'exact_int/broadcast',
    'exact_int/shaped_broadcast',
    'bigint/above_int64_paths',
]


def test_exact_loop_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
