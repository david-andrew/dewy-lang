"""Plan currency, tuple component facts, row bounds and assertion queueing agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'dogfood13_proofs/matching_rows',
    'effects/refined_param_proven',
    'dogfood23_proofs/pair_tuples_keep_bounds',
    'comptime/divide_zero',
    'dogfood13_proofs/short_rows',
    'dogfood23_proofs/pair_tuples_stored',
]


def test_facts_plans_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
