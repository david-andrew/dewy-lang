"""Name suggestions and declared-elsewhere hints agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'dogfood31_proofs/string_brace_misspelling',
    'overload/unknown_named_argument',
    'empty_literal/no_context_let_rejected',
    'frontend/statements_statement_record_sibling_scope_3',
]


def test_checks_hints_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
