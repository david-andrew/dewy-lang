"""Keep isolated checker services bound to their existing effect doubles."""
from functools import lru_cache
import re
from pathlib import Path

# (each moved checking leaf's twin first uses the module it left: an isolated driver's table for that module stands for it)
CHECKS_HOMES = {path.stem: match[1] for path in (Path(__file__).resolve().parents[1] / 'compiler').glob('checks_*.jo')
                if (match := re.match(r"use '(\w+\.jo)'\n", path.read_text()))}

# (a leaf moved out of a Jo module without state of its own: an isolated build that has that module but
# not the leaf reads the leaf's functions from the module, a double or the real one)
LEAF_HOMES = {
    'unit_ops': 'units.jo',
    'float_ops': 'floats.jo',
    'facts_arith': 'facts.jo',
    'facts_collect': 'facts.jo',
    'reader_service_ops': 'dewy_reader_services.jo',
    'spirv_ops': 'spirv.jo',
    'type_ops': 'types.jo',
    'word_overflow': 'types.jo',
    'glsl_ops': 'glsl.jo',
    'msl_ops': 'msl.jo',
    'refine_ops': 'refine.jo',
    'safe_path_ops': 'safe_paths.jo',
    'ide_ops': 'ide.jo',
    'lsp_handlers': 'lsp.jo',
    'ide_index': 'ide.jo',
    'prelude_ops': 'prelude.jo',
    'exact_loop_ops': 'exact_loop.jo',
    'lsp_ops': 'lsp.jo',
    'dewy_node_ops': 'dewy_nodes.jo',
    'dewy_node_builds': 'dewy_nodes.jo',
    'ide_text': 'ide.jo',
    'lsp_text': 'lsp.jo',
    'lsp_requests': 'lsp.jo',
    'spirv_emit': 'spirv.jo',
    'glsl_emit': 'glsl.jo',
}


@lru_cache(maxsize=512)
def _doubled(text, names):
    """Whether a module's text defines one of these functions, a double of a moved leaf's."""
    return any('\n' + name + ' = ' in text for name in names)


def effect_services(text, modules):
    if 'main.jo' not in modules:
        for stem, home in CHECKS_HOMES.items():
            text = text.replace(stem + '.dewy', home).replace(stem + '.jo', home)
    if "ownership_finalize = " in modules.get("ownership.jo", ""):
        text = text.replace("ownership_hooks.dewy", "ownership.jo").replace(
            "ownership_hooks.jo", "ownership.jo")
    if any(name + " = " in modules.get("secrets.jo", "")
           for name in ("secret_cast", "secret_member", "secret_unary")):
        text = text.replace("secret_checks.dewy", "secrets.jo").replace(
            "secret_checks.jo", "secrets.jo")
    if 'dc_force_all = ' in modules.get('lazy_bodies.jo', ''):
        text = text.replace('lazy_force.dewy', 'lazy_bodies.jo').replace('lazy_force.jo', 'lazy_bodies.jo')
    if 'cc_call = ' in modules.get('check_constant.jo', '') or 'cc_reset = ' in modules.get('check_constant.jo', ''):
        text = text.replace('constant_checks.dewy', 'check_constant.jo').replace('constant_checks.jo', 'check_constant.jo')
    if 'ic_fn = ' in modules.get('icount.jo', '') or 'ic_mod = ' in modules.get('icount.jo', '') or 'ic_switch = ' in modules.get('icount.jo', ''):
        text = text.replace('icount_ops.dewy', 'icount.jo').replace('icount_ops.jo', 'icount.jo')
    if 'wi_reset = ' in modules.get('warn_if.jo', ''):
        text = text.replace('warn_if_ops.dewy', 'warn_if.jo').replace('warn_if_ops.jo', 'warn_if.jo')
    if any(name + ' = ' in modules.get('poly_closure.jo', '') for name in ('poly_matches', 'poly_inst', 'poly_fnref', 'poly_default_type', 'poly_default_variant', 'poly_finish_warnings', 'check_poly_lambda', 'poly_env_layout')):
        text = text.replace('poly_ops.dewy', 'poly_closure.jo').replace('poly_ops.jo', 'poly_closure.jo')
    if 'member_candidates = ' in modules.get('member_replay.jo', '') or 'member_reset = ' in modules.get('member_replay.jo', ''):
        text = text.replace('member_admit.dewy', 'member_replay.jo').replace('member_admit.jo', 'member_replay.jo')
    if 'juxt_' in modules.get('juxtapose.jo', '') and 'juxt_keywords' not in modules['juxtapose.jo']:
        text = text.replace('juxtapose.dewy', 'juxtapose.jo')
    if 'init_module_order = ' in modules.get('import_cycles.jo', ''):
        text = text.replace('cycle_ops.dewy', 'import_cycles.jo').replace('cycle_ops.jo', 'import_cycles.jo')
    if 'temperature_read = ' in modules.get('temperature_kinds.jo', ''):
        text = text.replace('temperature_ops.dewy', 'temperature_kinds.jo').replace('temperature_ops.jo', 'temperature_kinds.jo')
    if any(name + ' = ' in modules.get('string_domains.jo', '') for name in ('string_domain_members', 'int_domain_declare', 'string_domain_declare', 'string_domains_finish', 'int_domains_finish', 'string_domains_materialize')):
        text = text.replace('string_domain_ops.dewy', 'string_domains.jo').replace('string_domain_ops.jo', 'string_domains.jo')
    if any(name + ' = ' in modules.get('growth.jo', '') for name in ('growth_assign', 'growth_decl_before', 'growth_decl_after', 'growth_flush')):
        text = text.replace('growth_ops.dewy', 'growth.jo').replace('growth_ops.jo', 'growth.jo')
    if any(name + ' = ' in modules.get('sibling_types.jo', '') for name in ('sibling_array_source', 'sibling_annotated', 'sibling_syntax_type', 'sibling_scalar', 'sibling_binding', 'sibling_statement')):
        text = text.replace('sibling_ops.dewy', 'sibling_types.jo').replace('sibling_ops.jo', 'sibling_types.jo')
    if any(name + ' = ' in modules.get('reflection.jo', '') for name in ('reflect_fields', 'reflect_members', 'members_argument', 'members_named', 'reflect_member', 'members_array', 'reflect_record', 'reflect_loop')):
        text = text.replace('reflect_ops.dewy', 'reflection.jo').replace('reflect_ops.jo', 'reflection.jo')
    if _doubled(modules.get('errors.jo', ''), ('exception_builtins', 'nominal_descends', 'exception_member', 'value_members', 'nominal_family', 'nominal_family_part', 'exception_join', 'members_within', 'nominal_resolve', 'mint_of_any', 'prepare_nominals', 'nominal_generic_parent', 'nominal_instance', 'family_holds_generic', 'nominal_generic_instance', 'infer_throw', 'infer_note_return', 'infer_finish', 'check_propagate', 'propagate_inferring', 'propagate_error', 'propagate_rewrite', 'oom_unhandled', 'forward_member', 'forwards_exceptions', 'forward_call', 'family_annotation', 'nominal_declaration')):
        text = text.replace('error_ops.dewy', 'errors.jo').replace('error_ops.jo', 'errors.jo')
    if _doubled(modules.get('dewy_methods.jo', ''), ('dewy_inherited_key', 'dewy_defer_type', 'dewy_deferred_here', 'dewy_defer_name', 'dewy_defer_callee', 'dewy_resolve_inherited', 'dewy_inherit', 'dewy_parent_decl', 'dewy_is_method', 'dewy_method_group', 'dewy_demand_receivers', 'dewy_infer_methods', 'dewy_reads', 'dewy_type_method', 'dewy_method_changes', 'dewy_reachable_from', 'dewy_route_root', 'dewy_reaches', 'dewy_member_changes', 'dewy_change_found', 'dewy_member_closures', 'dewy_member_closure_names', 'dewy_member_closure_handles', 'dewy_route_member', 'dewy_changes', 'dewy_changes_within')):
        text = text.replace('dewy_method_ops.dewy', 'dewy_methods.jo').replace('dewy_method_ops.jo', 'dewy_methods.jo')
    if _doubled(modules.get('decimals.jo', ''), ('decimal_let', 'decimal_binding_in', 'decimal_lambda_in', 'decimal_wants', 'decimal_save', 'decimal_copy', 'decimal_drop', 'decimal_marks', 'decimal_made_here', 'decimal_requests', 'decimal_restore', 'decimal_check_body', 'decimal_watch', 'decimal_root', 'decimal_binding_type', 'decimal_local', 'decimal_global', 'decimal_use', 'decimal_assign_begin', 'decimal_float_write', 'decimal_nested_in_frame', 'decimal_writers_first', 'decimal_input_globals', 'decimal_writes', 'decimal_adapted_warn', 'decimal_compared')):
        text = text.replace('decimal_ops.dewy', 'decimals.jo').replace('decimal_ops.jo', 'decimals.jo')
    if _doubled(modules.get('copies.jo', ''), ('copies_reset', 'copy_consumes', 'copy_escapes', 'copies_parameters', 'copy_strict', 'costly_copy', 'copy_error', 'copy_reason', 'copy_children', 'copy_mentions', 'copy_field', 'copy_field_live', 'copy_local_live', 'copy_kill_local', 'copy_live', 'copies_prepare', 'copy_deferred', 'copy_take', 'copy_forget', 'copy_movable', 'copy_later_use', 'copy_own', 'copy_components', 'own_at', 'copy_readonly', 'copy_shared_decl', 'copy_shared_global', 'copy_loop_locals', 'copy_capture_ids')):
        text = text.replace('copy_ops.dewy', 'copies.jo').replace('copy_ops.jo', 'copies.jo')
    if _doubled(modules.get('partition.jo', ''), ('partition_scalar', 'partition_slice', 'partition_root', 'partition_bound', 'partition_disjoint', 'partition_parameter', 'partition_formal', 'partition_body', 'partition_function', 'partition_descriptor', 'partition_arg', 'partition_call_needed', 'partition_call', 'partition_arm', 'partition_shared_root', 'partition_fork', 'partition_fork_calls', 'partition_fork_safe', 'partition_local_arg', 'partition_finalize', 'partition_begin', 'partition_inline_body')):
        text = text.replace('partition_ops.dewy', 'partition.jo').replace('partition_ops.jo', 'partition.jo')
    if _doubled(modules.get('inline.jo', ''), ('fast_callback_movable', 'fast_moves_alone', 'fast_inline_kind', 'fast_plain_kind', 'fast_inline_prepare', 'rel_collect', 'inlinable', 'inline_branch_mask', 'inline_cache_clear', 'inline_target', 'inline_callee')):
        text = text.replace('inline_ops.dewy', 'inline.jo').replace('inline_ops.jo', 'inline.jo')
    if _doubled(modules.get('proofs.jo', ''), ('proof_term', 'proof_walk', 'proof_visit', 'proof_prepare', 'proof_predicate', 'proof_require', 'proof_exit', 'proof_call', 'proof_erase', 'result_signature', 'result_tag', 'result_selector', 'result_exit', 'result_publish', 'ref_arm_publish', 'ref_refined_arms', 'ref_refined_result', 'result_activate', 'proof_reset', 'proof_atom_type', 'result_replaced')):
        text = text.replace('proof_ops.dewy', 'proofs.jo').replace('proof_ops.jo', 'proofs.jo')
    if _doubled(modules.get('witness.jo', ''), ('wit_skip_uses', 'wit_skip_close', 'wit_fail', 'wit_note', 'wit_help', 'wit_op', 'wit_hidden_read', 'wit_same_value', 'wit_operand', 'wit_lent', 'wit_quoted', 'wit_call_text', 'wit_event', 'wit_reason', 'wit_cause', 'wit_context', 'wit_projection', 'wit_tomb', 'wit_operand_changed', 'wit_call_node', 'wit_call_writes', 'wit_owner_calls', 'wit_leaves', 'wit_reaches', 'wit_projection_call', 'wit_value', 'wit_known', 'wit_holds', 'wit_candidates', 'wit_counterexample', 'wit_same', 'wit_guard', 'wit_orient', 'wit_relation_text', 'wit_constant', 'wit_relation', 'wit_unknown', 'wit_field_divisor_help', 'wit_counter_help', 'wit_int_parameter_help', 'wit_side', 'wit_comparison', 'wit_status', 'wit_connective', 'wit_assertion', 'wit_index', 'wit_parameter_lower_help', 'wit_position_help', 'wit_key', 'wit_constant_keys', 'wit_operation', 'wit_held_name', 'wit_slice', 'wit_clamp_help', 'wit_divisor', 'wit_ref_text', 'wit_ref_side', 'wit_call_holding', 'wit_refinement', 'wit_formal_text', 'wit_proof')):
        text = text.replace('witness_ops.dewy', 'witness.jo').replace('witness_ops.jo', 'witness.jo')
    if _doubled(modules.get('directives.jo', ''), ('directives_reset', 'dir_names', 'dw_dir_known', 'dir_valued_name', 'dir_valued_check', 'dir_scope_written', 'version_well_formed', 'version_newer', 'toolchain_version', 'toolchain_tagged', 'dir_zone_pin', 'dir_version_warnings', 'dir_bundle_index', 'dir_bundle_resolve', 'dir_bundle_merge', 'dir_bundles_resolve', 'dir_force', 'dir_spelled', 'dir_conflict', 'dir_push', 'dir_set', 'dir_obligation_text', 'directives_after_facts', 'dir_policy_name', 'dir_print_obligations', 'dir_panics_finalize', 'dir_panic_source', 'dir_panic_call', 'dir_panic_fix', 'dir_assume_local_asserts', 'dir_confine_paths', 'dir_no_deadlocks', 'dir_audited_wait', 'dir_row_origin')):
        text = text.replace('directive_ops.dewy', 'directives.jo').replace('directive_ops.jo', 'directives.jo')
    if _doubled(modules.get('facts.jo', ''), ('fact_fork_record', 'fact_parallel_array', 'fact_parallel_record', 'fact_key_callback', 'fact_key_record', 'fact_fork_seed', 'fact_call_arguments', 'fact_slice_capture')):
        text = text.replace('facts_forks.dewy', 'facts.jo').replace('facts_forks.jo', 'facts.jo')
    if _doubled(modules.get('facts.jo', ''), ('fact_replace', 'fact_read', 'fact_constant_global', 'fact_constant_tree', 'fact_global_integer', 'fact_global_length', 'fact_receiver_route', 'fact_route', 'fact_after_call', 'fact_route_values', 'fact_store_route', 'fact_component', 'fact_store_pattern', 'fact_route_bounds')):
        text = text.replace('facts_routes.dewy', 'facts.jo').replace('facts_routes.jo', 'facts.jo')
    if _doubled(modules.get('facts.jo', ''), ('fact_range_call', 'fact_range_first', 'fact_stepped_loop', 'fact_open_range', 'fact_range_assumed', 'fact_range_exhaustion', 'fact_step_check', 'fact_nonnegative', 'fact_refinement_covers', 'fact_host_value', 'fact_host_endpoint', 'fact_narrow_check', 'fact_floor_call', 'fact_range')):
        text = text.replace('facts_ranges.dewy', 'facts.jo').replace('facts_ranges.jo', 'facts.jo')
    if _doubled(modules.get('facts.jo', ''), ('fact_scaled_again', 'fact_scaled_open', 'fact_scaled_quotient', 'fact_word_type', 'fact_open_product', 'fact_reuse_tighten', 'fact_open_bound', 'fact_offset_value', 'fact_divisor', 'fact_quotient', 'fact_sum_quotient_endpoint', 'fact_sum_quotient', 'fact_floor', 'fact_quotient_divisor', 'fact_midpoint', 'fact_floor_unsigned', 'fact_bitwise', 'fact_extremum_call', 'fact_extremum', 'fact_rational_zero_test', 'fact_rational_constructor', 'fact_rational_divmod', 'fact_quantity_number', 'fact_rational_promotion', 'fact_rational_made', 'fact_power_call', 'fact_power_check', 'fact_holds_implication', 'fact_power_rational', 'fact_shift_obliged')):
        text = text.replace('facts_numeric.dewy', 'facts.jo').replace('facts_numeric.jo', 'facts.jo')
    if _doubled(modules.get('facts.jo', ''), ('fact_plan_current', 'fact_component_selector', 'fact_component_fact', 'fact_int_rows', 'fact_int_component', 'fact_int_components', 'fact_component_bounds', 'fact_row_bounds', 'fact_open', 'fact_pure', 'fact_queue')):
        text = text.replace('facts_plans.dewy', 'facts.jo').replace('facts_plans.jo', 'facts.jo')
    if _doubled(modules.get('facts.jo', ''), ('fact_written_root', 'fact_routed_write', 'fact_routed_place', 'fact_forget_call', 'fact_dewy_local', 'fact_disjoint', 'fact_exposed_bound', 'fact_forget', 'fact_sink_disjoint_param', 'fact_owner_in_lib', 'fact_fn_in_lib', 'fact_holds_contract', 'fact_ends_path', 'fact_path_call_effects', 'fact_call_effects', 'fact_builtin_formatter', 'fact_text_sink', 'fact_call_field_type', 'fact_call_write')):
        text = text.replace('facts_forgets.dewy', 'facts.jo').replace('facts_forgets.jo', 'facts.jo')
    if _doubled(modules.get('facts.jo', ''), ('fact_parallel_range_call', 'fact_through_conv', 'fact_parallel_count_check', 'fact_bounded_index', 'fact_scope_exit', 'fact_refinements_unreachable', 'facts_finalize', 'facts_reset', 'fact_owner_value', 'fact_forget_hooked', 'fact_literal_nonzero', 'fact_complete_deferred')):
        text = text.replace('facts_lifecycle.dewy', 'facts.jo').replace('facts_lifecycle.jo', 'facts.jo')
    for leaf, home in LEAF_HOMES.items():
        if home in modules and leaf + '.dewy' not in modules and leaf + '.jo' not in modules:
            text = text.replace(leaf + '.dewy', home).replace(leaf + '.jo', home)
    if 'struct ParSafeVia:' not in modules.get('concurrency.jo', ''):
        for stem in ('concurrency_types', 'concurrency_tasks'):
            text = text.replace(stem + '.dewy', 'concurrency.jo').replace(
                stem + '.jo', 'concurrency.jo')
    if 'struct IsolationRow:' not in modules.get('isolation.jo', ''):
        text = text.replace('isolation_ops.dewy', 'isolation.jo').replace(
            'isolation_ops.jo', 'isolation.jo')
    # Whole-compiler differentials supply the real state and switch one leaf.
    # Isolated checker drivers instead own only the effect callbacks they use.
    if 'struct EffectSummary:' in modules.get('effects.jo', ''):
        return text
    for stem in ('effect_contracts', 'effect_control', 'effect_sources'):
        text = text.replace(stem + '.dewy', 'effects.jo').replace(
            stem + '.jo', 'effects.jo')
    return text


def type_helpers_home(text):
    """An isolated harness whose types.jo is a double reads the moved type helpers from that double."""
    for stem in ('type_ops', 'word_overflow'):
        text = text.replace(stem + '.dewy', 'types.jo').replace(stem + '.jo', 'types.jo')
    return text
