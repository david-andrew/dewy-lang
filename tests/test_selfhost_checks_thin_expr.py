"""Thin expression helpers and their diagnostics agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'frontend/flows_flow_fallback_diagnostics_3',
    'refine_alias_tags/element_nested_field',
    'frontend/statements_statement_record_sibling_scope_1',
    'errors/ndarray_rational_hint',
    'units/mismatch_assign',
    'frontend/declarations_declaration_fallback_7',
    'errors/set_call_non_member',
    'numeric/broadcast_matrix_selection_constant',
    'frontend/strings_string_diagnostics_4',
    'effects/input_int_no_traps',
    'secret/ordering_condition',
    'new_axis/too_many_axes',
    'gpu/array_exact_division',
    'dogfood30_proofs/vector_lane_search_rejected',
    'deadlock/hidden_hash',
    'singleton/string_set_superset_arms',
    'exact_int/shaped_broadcast',
    'float_constants/reject_unknown_limit',
    'fixed/array_wrong_length',
    'handle/partial_generic_unknown',
    'handle/field_needs_arguments',
    'tasks/spawn_assigned',
    'ownership/hook_value_preservation',
    'argument/mutable_same_element',
    'singleton/string_set_no_numbers_as',
    'surface/len_protocol',
    'facts/nd_slice_deferred_storage',
    'singleton/optional_literal_union_argument',
    'float/literal_overflow',
    'new_axis/selections',
    'handle/keeps_defaults',
    'errors/void_union_print',
    'inference/then_branch_literal',
    'coalesce/listed_kinds',
    'search/missing',
    'game/polyline_joins',
    'frontend/flows_flow_fallback_diagnostics_5',
    'units/mixed_array',
    'multi/written_mixed_types_hint',
    'handle/closure_needs_arguments',
    'handle/function_expected',
    'object/const_receiver',
]


def test_checks_thin_expr_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
