"""Pool membership facts agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'collections/library_length',
    'facts/pool_removed_handle',
    'notraps12/pool_callee_reject',
    'witness/nested_key_relation',
]


def test_facts_pools_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
