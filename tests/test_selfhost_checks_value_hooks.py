"""Value expression services and errors agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'frontend/declarations_declaration_fallback_7',
    'misc/main_record_result',
    'frontend/declarations_declaration_fallback_6',
    'frontend/flows_flow_fallback_diagnostics_5',
    'frontend/statements_statement_record_sibling_scope_1',
    'multi/pack_one_value',
    'fixed/array_spread_context',
    'misc/unary_plus_text',
    'positional/wrong_length',
    'partial/operator_missing_context',
    'record/spread_array',
    'positional/siblings_insert',
    'handle/partial_ambiguous',
    'generic/operator_arithmetic',
    'directives/no_inf_caller',
    'rational/error_4',
    'dogfood24_proofs/field_keys_other_field',
    'facts/nd_slice_contracts',
    'units/conversions',
    'frontend/flows_flow_fallback_diagnostics_3',
    'membership/callable_field',
    'frontend/strings_string_diagnostics_4',
    'closure/capture_each_name',
    'frontend/m_directives_migrated_directives_diagnostics_10',
    'generic/constructor_conflicting_callback',
    'empty_literal/no_context_let_rejected',
    'frontend/m_directives_migrated_directives_diagnostics_13',
    'misc/hex_too_large',
    'record_in_array/reject_for_array',
]


def test_checks_value_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
