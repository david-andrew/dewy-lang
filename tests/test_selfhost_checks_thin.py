"""Thin checking helpers and their diagnostics agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'frontend/declarations_declaration_fallback_7',
    'numbers/int_accumulator_decimal',
    'constant/shadowable_import_const',
    'main/explicit_call_rejected',
    'dogfood18_proofs/alias_refinement_self',
    'frontend/flows_flow_fallback_diagnostics_4',
    'fixed/array_spread_context',
    'multi/pack_one_value',
    'refine_alias_tags/tag_alias_optional_reject',
    'method/indirect_mutating_loop',
    'refinement_aggregates/sibling_rejected',
    'match/family_parent_arm',
    'constant/literal_assign',
    'multi/values_block_branch',
    'object/recursive_literal_return',
    'multi/void_body_value',
    'place_method/misuse_operand',
    'spread/record_arguments',
    'multi/one_value_block',
    'witness/pool_update_callee',
    'juxtaposition/spaced_unit',
    'frontend/declarations_declaration_fallback_6',
    'comptime/host_effect',
    'refine_alias_tags/element_nested_field',
    'main/expressed_mixed_values',
    'rational/library_word_name',
    'a=[1 2]\nb=[3]\nf=(x:int y:int)=>x+y\nprintl(f(a... b...))\n',
    'f=(x:int)=>x\nprintl(f(3...))\n',
    'f=()=>{\n    1\n    "a"\n}\nprintl(f())\n',
    'f=()=>{\n    1\n    return 2\n}\nprintl(f())\n',
]


def test_checks_thin_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
