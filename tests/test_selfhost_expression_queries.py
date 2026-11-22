"""Check expression queries and their diagnostics against each frozen Jo leaf."""

import pytest

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize(("leaf", "cases"), [
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
