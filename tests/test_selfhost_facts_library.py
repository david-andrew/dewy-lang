"""Library call classifiers and contract facts agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'unpack/global_discard',
    'collections/library_length',
    'sequence/minmax_by_no_tail_allocation',
    'array/fill_flat',
    'misc/zero_divisor_remainder_uint64',
    'generic/array_literal_user_sum',
    'library_contracts/sum_exact_bounds',
    'refine_dependent_alias/sibling_method_ok',
    'facts/repeated_array_endpoints',
    'dogfood27_proofs/sum_lengths_hint',
]


def test_facts_library_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
