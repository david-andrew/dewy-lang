"""Refinement interning, refined-type construction and state reset agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401

LEAVES = ('refine_metadata', 'refine_rare')
# Interned contracts from declarations, N-D shapes, reflection singletons, integer type
# arguments, text-search facts and proofs; every program starts from a reset state.
PATTERNS = ('refinements/*.dewy', 'nd_contracts/*.dewy', 'refine_generic_*/*.dewy',
            'uint64_ceiling/*.dewy', 'default_proofs/*.dewy', 'self_length/decl_*.dewy',
            'reflect_types/*.dewy', 'type_members/*.dewy')


def test_refine_interning_program_twins(compiler, tmp_path, monkeypatch):
    found = {str(p.relative_to(ROOT / 'tests/cases'))[:-5]
             for pattern in PATTERNS for p in (ROOT / 'tests/cases').glob(pattern)}
    assert compare_facts(compiler, tmp_path, monkeypatch, sorted(found), leaves=LEAVES) > 60
