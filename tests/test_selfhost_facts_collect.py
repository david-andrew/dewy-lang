"""State compaction, scope collection, decided remainders and guarded words agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'refinements/later_dependent',
    'effects/slice_assign_fixed_no_traps',
    'numeric/bounded_remainder_overflow',
    'facts/matrix_product_contracts',
    'dogfood36_proofs/remainder_decides_bounds',
    'singleton/integer_union_refuted',
    'facts/nonlinear',
    'facts/nd_stepped_assignment_count',
]


def test_facts_collect_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
