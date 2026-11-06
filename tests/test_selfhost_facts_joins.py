"""Branch joins and hulls agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'optional/optional_plain_strict',
    'coalesce/basic',
    'misc/empty_dictionary',
    'facts/pool_calls_effects',
    'dogfood29_proofs/optional_best_join',
]


def test_facts_joins_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
