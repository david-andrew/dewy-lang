"""Keep isolated checker services bound to their existing effect doubles."""
from functools import lru_cache


@lru_cache(maxsize=512)
def _doubled(text, names):
    """Whether a module's text defines one of these functions, a double of a moved leaf's."""
    return any('\n' + name + ' = ' in text for name in names)


def effect_services(text, modules):
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
