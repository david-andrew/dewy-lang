"""Partitioned slices agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'argument/mutable_param_entry_global_write',
    'argument/mutable_borrowed_params',
    'exact_int/parallel_result',
    'method/hidden_global_loop',
    'parallel/param_reassigned',
    'bench/parallel/mergesort.dewy',
    'bench/parallel/jacobi.dewy',
    'tests/ladder/82_overlap_race/core.dewy',
]


def test_partition_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
