"""Assignment, block and sink services agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'multi/values_binding_type_place',
    'multi/pack_one_value',
    'refine_alias_tags/element_nested_field',
    'frontend/declarations_declaration_fallback_7',
    'multi/handle_one_value',
    'dogfood20_proofs/sort_key_parts',
    'multi/void_failure_statement',
    'unpack/values_sources',
    'multi/values_operand',
    'multi/values_dynamic',
    'positional/siblings_flow_branch',
    'dogfood31_proofs/key_in_loop_hint',
    'multi/values_spread_length',
    'refinements/cycle',
    'dictionary/totaldict_pop',
    'multi/mixed_types',
    'multi/void_body_value',
    'multi/written_one_value',
    'multi/or_throw_expressed',
    'multi/values_index',
    'multi/values_lambda_count',
    'array/no_plus_assign',
    'inference/mutual_recursion_no_base',
    'multi/values_binding_type_count',
]


def test_checks_assign_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
