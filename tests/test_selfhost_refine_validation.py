"""Signature and record validation, storage contracts and nested formals agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401

LEAVES = ('refine_metadata',)
# Rejected declarations: cyclic, mutable, nested-formal and self-naming contracts.
CASES = [
    'dogfood18_proofs/alias_refinement_self',
    'mutable_entry_contract/mutable_index',
    'mutable_entry_contract/mutable_scalar_bound',
    'refinements/cycle',
    'refinements/dependent_array_result',
    'self_length/decl_callable_formal',
    'self_length/decl_lambda_parameter',
    'self_length/decl_other_parameter',
]
# Accepted dependent signatures and records, storage contracts and field shapes.
PATTERNS = ('refinements/*.dewy', 'sibling_length/*.dewy', 'dict_sibling/*.dewy', 'record_paired_fields/*.dewy',
            'record_field_shape/*.dewy', 'refine_dependent_alias/*.dewy', 'nd_contracts/*.dewy',
            'mutable_entry_contract/*.dewy', 'self_length/decl_*.dewy')


def test_refine_validation_program_twins(compiler, tmp_path, monkeypatch):
    found = {str(p.relative_to(ROOT / 'tests/cases'))[:-5]
             for pattern in PATTERNS for p in (ROOT / 'tests/cases').glob(pattern)}
    assert compare_facts(compiler, tmp_path, monkeypatch, sorted(found | set(CASES)), leaves=LEAVES) > 60
