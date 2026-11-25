"""Compare expression coercion, call and indexing decisions with their frozen implementations."""

import pytest

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize(("leaf", "cases"), [
    ("array_element_conversion", (
        "refine_array_widening/values",
        "refine_array_widening/mutable_rejected",
        "refine_array_widening/copies",
        "refine_array_widening/looser_rejected",
        "refine_array_widening/length_rejected",
    )),
    ("record_construction", (
        "record/context_order",
        "record/bare_defaults",
        "record/bare_required",
        "generic_record_defaults/defaults",
        "generic_record_defaults/overflow",
        "default/field_earlier",
    )),
    ("rational_lookup", (
        "rational/abs_min_max_sign",
        "rational/library_name",
        "rational/library_word_name",
        "rational/mixed",
        "rational/division_generic_mixed",
        "overload/user_shadows_prelude",
    )),
    ("position_indexing", (
        "tuple_slot_write/index_once",
        "tuple_slot_write/proven_bound",
        "tuple_slot_write/string_position_rejected",
        "dogfood23_proofs/pair_tuples_stored",
        "dogfood23_proofs/pair_tuples_off_by_one",
    )),
    ("numeric_branch_queries", (
        "generic/array_literal_float_overload",
        "generic/array_literal_bound_scalar_overload",
        "overload/group_types",
        "overload/group_unsigned_literal",
    )),
    ("integer_call_folds", (
        "floor_remainder/negative",
        "floor_remainder/negative_divisor",
        "floor_remainder/zero_divisor",
        "power/exact",
        "power/negative_constant_exponent",
    )),
    ("game_call_checks", (
        "method/named_update_draw",
        "deadlock/cancel_cleanup",
        "deadlock/grant_cancel",
    )),
    ("integer_conversions", (
        "conversion/int_boundary_diagnostic",
        "conversion/int_parameter_width",
        "conversion/checked_narrowing",
        "numbers/int_conversions",
        "overload/group_unsigned_literal",
    )),
    ("numeric_library_types", (
        "bigint/builtin_members",
        "bigint/above_int64_paths",
        "bigint/conversions",
        "bigint/dogfood14_gcd_shadow",
        "power/exact",
    )),
    ("union_conversion_nodes", (
        "literal_union_outcomes/merged_match",
        "refine_union_storage/union_store_ok",
        "refine_union_storage/union_store_reject",
        "floor_remainder/negative_divisor",
        "anonymous_record_union/context",
    )),
    ("collection_cancellation", (
        "explicit_cancellation/collector",
        "explicit_cancellation/spread",
        "explicit_cancellation/loop_collector",
        "explicit_cancellation/nested",
        "explicit_cancellation/accepted",
    )),
    ("aggregate_sources", (
        "decided_array_separators/record_spreads",
        "spread/arrays",
        "spread/empty_context",
        "spread/order_snapshot",
        "spread/record_arguments",
        "set/context_comparison",
    )),
], ids=lambda arg: arg if isinstance(arg, str) else None)
def test_expr_conversion_twins(compiler, tmp_path, monkeypatch, leaf, cases):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, leaf, cases)
