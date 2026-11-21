"""Compare expression receivers, literal checks, and argument lookup with their Jo twins."""

import pytest

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize(("leaf", "cases"), [
    ("set_type_queries", (
        "set/algebra",
        "set/context_comparison",
        "set/copy_and_removal",
        "set/custom_hash",
        "set/comprehension_and_generic",
    )),
    ("argument_order", (
        "default/reference_named",
        "select_named/named",
        "select_named/captured",
        "select_named/changed",
        "overload/group_arity",
    )),
    ("literal_context", (
        "rational/word",
        "empty_literal/dict_contexts",
        "generic/array_literal_deferred_float",
        "conversion/int_boundary_diagnostic",
        "overload/group_unsigned_literal",
    )),
    ("call_lookup_context", (
        "path/import_source",
        "path/literal_beside_p_binding",
        "path/interpolation",
        "overload/user_shadows_prelude",
        "style/zero_argument_calls",
    )),
    ("member_receivers", (
        "style/zero_argument_calls",
        "record/function_field_shadowed",
        "singleton/receiver_literal_takes_result_type",
        "path/file_methods",
        "end/index_slices",
    )),
    ("path_narrowing", (
        "census_proofs/narrowing_field_proven",
        "census_proofs/narrowing_field_named",
        "optional/fill_join",
        "match/family_parent_arm",
        "refine_union_storage/union_store_reject",
    )),
    ("conditional_narrowing", (
        "optional/fill_join",
        "match/family_parent_arm",
        "census_proofs/narrowing_field_proven",
        "array/comparison_conditional_empty",
    )),
    ("rational_lookup", (
        "rational/abs_min_max_sign",
        "rational/library_word_name",
        "rational/library_name",
        "rational/division_generic_mixed",
        "overload/user_shadows_prelude",
    )),
    ("call_argument_checks", (
        "generic/array_literal_deferred_float",
        "generic/array_literal_concrete_overload",
        "overload/unknown_named_argument",
        "select_named/named",
        "default/reference_named",
    )),
], ids=lambda arg: arg if isinstance(arg, str) else None)
def test_expr_receiver_twins(compiler, tmp_path, monkeypatch, leaf, cases):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, leaf, cases)
