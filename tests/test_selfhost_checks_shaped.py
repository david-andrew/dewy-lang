"""Shape-covered matches agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'match/object_pattern_gap',
    'singleton/mixed_literal_union_gap',
    'match/sequence_tuple_positions',
    'dogfood36_proofs/optional_union_guard_gap_rejected',
    'match/shape_unreachable_member',
    'dogfood36_proofs/optional_union_uncovered_rejected',
    'match/union_bool_incomplete',
    'match/sequence_unreachable',
    'match/tuple_fields',
    'match/unreachable_after_wild',
]


def test_checks_shaped_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
