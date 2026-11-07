"""Match hooks and exhaustiveness errors agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'facts/match_arm',
    'match/named_catch_all_rest',
    'match/wild_optional_union_rest_path',
    'errors/string_literal_match_hint',
    'match/unreachable_after_wild',
    'match/union_bool_incomplete',
    'match/optional_missing_none',
    'match/union_subset_copy',
    'match/incomplete',
    'singleton/mixed_literal_union_gap',
    'dogfood34_proofs/unsigned_literal_exhaustive',
    'match/sequence_unreachable',
    'dogfood36_proofs/optional_union_uncovered_rejected',
]


def test_checks_match_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
