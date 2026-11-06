"""Keep isolated checker services bound to their existing effect doubles."""


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
