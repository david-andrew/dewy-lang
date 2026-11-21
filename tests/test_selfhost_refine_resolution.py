"""Refinement resolution, coercion, projection types and span copies agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401

LEAVES = ('refine_rare',)
# Declared contracts (scalar, dependent, aliased, generic, self-length, total dictionary,
# SafePath and string-domain), their coercions and the projections they name.
PATTERNS = ('refinements/*.dewy', 'refine_dependent_alias/*.dewy', 'refine_alias_*/*.dewy',
            'refine_generic_*/*.dewy', 'dict_refine/*.dewy', 'dictionary/totaldict*.dewy',
            'decided_path_contracts/*.dewy', 'uint64_ceiling/*.dewy', 'refinement_unknown_name/*.dewy',
            'self_length/decl_*.dewy')


def test_refine_resolution_program_twins(compiler, tmp_path, monkeypatch):
    found = {str(p.relative_to(ROOT / 'tests/cases'))[:-5]
             for pattern in PATTERNS for p in (ROOT / 'tests/cases').glob(pattern)}
    assert compare_facts(compiler, tmp_path, monkeypatch, sorted(found), leaves=LEAVES) > 80
