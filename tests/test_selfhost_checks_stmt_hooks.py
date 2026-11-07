"""Statement, loop, declaration, return and body services agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'frontend/flows_flow_fallback_diagnostics_4',
    'refine_alias_tags/element_nested_field',
    'frontend/flows_flow_fallback_diagnostics_2',
    'surface/recursive_alias_record',
    'comptime/mutable_global',
    'errors/mixed_pair_tuple_hint',
    'multi/pack_one_value',
    'numbers/int_accumulator_decimal',
    'queues/spsc_capacity',
    'inference/mutual_recursion_no_base',
    'loop/label_duplicate',
    'definite/container',
    'loop/else_argument_exit',
    'comprehension/collects_nothing',
    'frontend/m_statements_migrated_statements_diagnostics_1',
    'juxtaposition/whitespace_product',
    'place_method/escape_local',
    'effects/declared_row_resource',
    'misc/nested_combined',
    'units/exact_update_float',
    'frontend/flows_flow_fallback_diagnostics_5',
    'frontend/declarations_declaration_fallback_7',
    'frontend/flows_flow_fallback_diagnostics_3',
    'empty_literal/no_context_let_rejected',
    'frontend/flows_flow_fallback_diagnostics_9',
    'frontend/statements_statement_diagnostics_3',
]


def test_checks_stmt_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
