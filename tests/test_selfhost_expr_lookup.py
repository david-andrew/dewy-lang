"""Compare the expression checker's lookup and construction paths with their frozen Jo twins."""

import pytest

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize(("leaf", "cases"), [
    ("call_shape_queries", ("style/zero_argument_calls", "overload/group_arity", "overload/group_defaults",
                            "record/function_field_shadowed", "generic/constructor_collections")),
    ("call_lookup_context", ("overload/user_shadows_prelude", "overload/group_generic",
                             "hookcalls/pool_factory", "dogfood/39_crafting_pool")),
    ("literal_context", ("empty_literal/dict_contexts", "empty_literal/record_contexts", "match/integers",
                         "array/comparison_conditional_empty", "generic/array_literal_bound_scalar_overload",
                         "string_union/literal_member", "string_union/reject_unlisted_literal")),
    ("callable_compatibility", ("callable/value_variance", "callable/handle_variance", "callable/return_handle",
                                "callable/prelude_collision_ambiguous", "generic/constructor_callbacks")),
    ("operator_lookup", ("generic/operator_arithmetic", "generic/operator_bits", "generic/operator_comparison",
                         "generic/operator_source_order", "misc/operator_comparison_result")),
    ("policy_value_queries", ("coverweek/time_fold_captured_value", "time_policy_literals/scoped_policies",
                              "partial/method_handle")),
    ("record_construction", ("record/anonymous_nested", "record/context_order", "record/bare_defaults",
                             "record/bare_required", "generic_record_defaults/defaults")),
    ("task_failure_values", ("queue_cancel_wait/task_failure_cancels_sibling", "queue_cancel_wait/failure_helper",
                             "queue_cancel_wait/channel_failure_diag", "tasks/first_ok_race_many")),
], ids=lambda arg: arg if isinstance(arg, str) else None)
def test_expr_lookup_twins(compiler, tmp_path, monkeypatch, leaf, cases):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, leaf, cases, flags=((), ("--release",)))
