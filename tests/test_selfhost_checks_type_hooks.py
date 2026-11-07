"""Type resolution, field, signature and instance services agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'surface/recursive_alias_record',
    'dogfood18_proofs/alias_refinement_self',
    'object/intersection_never',
    'refine_alias_tags/element_nested_field',
    'main/exit_code_member_cap',
    'multi/values_binding_type_place',
    'multi/written_mixed_types',
    'inference/empty_interpolated',
    'inference/mutual_recursion_no_base',
    'search/regex_too_big',
    'inference/recursive_value',
    'syntax/function_type_parens',
    'misc/main_record_result',
    'dictionary/totaldict_missing',
    'multi/written_mixed_types_hint',
    'frontend/migrated_migrated_diagnostics_8',
    'misc/proof_directive',
    'rational/word_width',
]


def test_checks_type_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
