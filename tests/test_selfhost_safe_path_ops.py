"""Safe-path tracking helpers (origins, marks, queues, path and text types, diagnostics) agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'contained/handler',
    'match/void_union_trailing_family',
    'contained/unproven_let',
    'contained/unproven_argument',
    'contained/unproven_result',
]


def test_safe_path_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
