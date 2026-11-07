"""Value and array unpacking agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'unpack/nested_scalar',
    'unpack/rest',
    'unpack/values_count',
    'unpack/missing_field',
    'search/regex_too_big',
    'unpack/leaf_discard_incompatible',
    'dogfood16_proofs/record_unpack_position',
    'surface/index_optional_member',
    'dogfood25_proofs/conditional_literal_length_mismatch',
    'positional/siblings_branch_push',
]


def test_checks_unpack_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
