"""Check expression queries and their diagnostics against each frozen Jo leaf."""

import pytest

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize(("leaf", "cases"), [
    ("struct_construction", ("object/zero_defaults", "object/positional_literal_extra", "generic/type_defaults")),
    ("explicit_conversions", ("conversion/float_int", "conversion/string_to_int_hint", "conversion/transmute_record")),
    ("arithmetic_calls", ("rational/powers", "exact_int/constant_width_reject_divide", "rational/mixed")),
    ("unresolved_call_names", ("ffi/intrinsic_unknown", "surface/missing_member", "overload/unknown_named_argument")),
    ("function_value_checks", ("overload/group_value", "overload/group_generic", "type_members/handles")),
    ("missing_member_checks", ("surface/missing_member", "surface/index_optional_member", "type_members/missing_member")),
    ("coerce_expression", ("conversion/int_float", "conversion/refuted_narrowing", "literal_union_proof/cast")),
    ("binary_operator_checks", ("exact_int/wide_modulo", "membership/return_type", "surface/compare_union_number")),
    ("intrinsic_expressions", ("ffi/intrinsic", "ffi/intrinsic_unknown", "word_format_local/finite")),
    ("integer_conversions", ("misc/narrow_integers", "exact_int/wrap_either_side")),
    ("coercion_queries", ("rational/float_array_argument_hint", "literal_union_proof/assignment")),
    ("storage_place_checks", ("grouped_place/routes", "grouped_place/misuse_operand")),
    ("overload_type_lookup", ("overload/group_types", "word_format_local/custom")),
    ("match_pattern_sets", ("literal_union_proof/sparse_guard", "literal_union_proof/changed_guard")),
    ("literal_context", ("default/reference_float", "exact_int/chain_exact_operands")),
    ("union_conversion_nodes", ("default_proofs/refuted_literal_union", "surface/union_operand_failure")),
    ("map_entry_places", ("dogfood24_proofs/dict_entries_then_insert", "unpack/dictionary_entries")),
    ("moved_argument_data", ("closure/default_callback_moved", "drop_footprints/move_hook_global")),
    ("path_narrowing", ("census_proofs/narrowing_field_proven", "witness/narrowed_place_contract")),
    ("call_lookup_context", ("overload/user_shadows_prelude", "surface/len_own")),
    ("set_type_queries", ("set/custom_hash", "set/copy_and_removal")),
    ("member_receivers", ("surface/len_member", "type_members/handles")),
    ("numeric_library_types", ("rational/matrix_of_fractions_prints", "rational/mixed")),
    ("argument_order", ("unpack/rest", "coverweek2/call_named_order")),
    ("call_shape_queries", ("constant/map_write", "exact_int/wrap_either_side")),
    ("call_argument_checks", ("default_proofs/lambda_needs_at", "coverweek2/call_missing_argument", "named/position_only_named")),
    ("aggregate_sources", ("type_members/records", "type_members/named_twice", "object/missing_field_positional")),
    ("member_handles", ("race_spread/no_calls", "race_spread/proven", "type_members/handles")),
    ("format_word_observations", ("word_format_local/finite", "word_format_local/fallback", "word_format_local/custom")),
    ("string_membership", ("singleton/membership_text_needle", "membership/dictionary", "membership/return_type")),
    ("index_operand_checks", ("surface/indexed_members", "surface/index_optional_member")),
    ("surface_names", ("surface/habit_open", "surface/len_call", "surface/python_string_methods")),
], ids=lambda value: value if isinstance(value, str) else None)
def test_expression_query_twins(compiler, tmp_path, monkeypatch, leaf, cases):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, leaf, cases)
