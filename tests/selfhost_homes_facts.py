"""Where a moved fact leaf's functions live in an isolated build that lacks the leaf."""
from tests.selfhost_homes_checks import _doubled

# (a leaf moved out of a Jo module without state of its own: an isolated build that has that module but
# not the leaf reads the leaf's functions from the module, a double or the real one)
LEAF_HOMES = {
    'facts_arith': 'facts.jo',
    'facts_row_queries': 'facts.jo',
    'facts_collect': 'facts.jo',
    'nd_contract_ops': 'nd_contracts.jo',
}


def facts_homes(text, modules):
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
    return text
