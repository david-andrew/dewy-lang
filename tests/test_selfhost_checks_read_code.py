"""Reader code for records and call description text agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'secret/leak_argument',
    'json/typed_defaults',
    'numbers/mod_kind_unknown',
    'errors/string_literal_match_hint',
    'units/parameter_mismatch',
    'numeric/negative_dimensions_literal',
    'optional/union_else_narrowing_path_write',
    'frontend/direct_direct_expression_diagnostics_4',
]


def test_checks_read_code_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
