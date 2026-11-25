"""Compare checker state transitions, lookup and type queries with their frozen Jo implementations."""

import pytest

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize(("leaf", "cases"), [
    ("checker_scope_symbols", (
        "block_scope/nested", "block_scope/shadowing", "census_proofs/narrowing_field_named",
    )),
    ("checker_contexts", ("path/import_source", "overload/user_shadows_prelude")),
    ("checker_module_lookup", ("import_cycles/interleaved", "overload/user_shadows_prelude")),
    ("checker_constant_queries", ("exact_int/chain_exact_operands", "default/reference_named")),
    ("checker_method_receiver", ("type_members/handles", "method/named_update_draw")),
    ("checker_type_entries", ("generic/type_defaults", "generic/value_wrong_type_count", "type_members/records")),
    ("checker_block_entries", ("block_scope/ownership", "block_scope/brace_keeps_names")),
    ("checker_import_discovery", ("path/import_source", "rational/library_word_name")),
    ("checker_binding_inputs", ("global/array_destructured_storage", "refine_destructure_storage/global_contract")),
    ("checker_source_positions", ("method/hidden_global_loop", "generic/type_defaults")),
    ("checker_narrow_writes", (
        "census_proofs/narrowing_field_proven", "refine_union_storage/union_store_reject",
    )),
    ("checker_captures", ("closure/alias_replacement", "closure/shared_function_cycle")),
    ("checker_loop_routes", ("method/mutating_loop", "dogfood28_proofs/match_in_loop_resize_rejected")),
    ("checker_value_protocols", ("set/custom_hash", "set/copy_and_removal")),
    ("checker_assignment_decls", ("exact_int/chain_exact_operands", "block_scope/shadowing")),
    ("checker_runtime_functions", ("exact_int/wrap_either_side", "rational/library_word_name")),
    ("checker_global_initialization", (
        "initorder/cycle_bad", "global/array_destructured_storage",
        "global/unset_read_at_top_level", "refine_destructure_storage/global_contract",
    )),
], ids=lambda item: item if isinstance(item, str) else None)
def test_checker_state_query_twins(compiler, tmp_path, monkeypatch, leaf, cases):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, leaf, cases)
