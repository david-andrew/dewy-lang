"""Self-length holders and refined array calls (insert, swap, reverse, sort) agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401

LEAVES = ('refine_rare',)
# Holder marking: self-length declarations, misplaced and doubled contracts, paired inserts,
# sibling permutations, private candidates and in-place swaps.
PATTERNS = ('self_length/*.dewy', 'sibling_length/*.dewy', 'dict_sibling/*.dewy',
            'record_paired_fields/*.dewy', 'length_in_place/*.dewy', 'refine_length_helpers/*.dewy',
            'sort/*.dewy')


def test_refine_array_call_program_twins(compiler, tmp_path, monkeypatch):
    found = {str(p.relative_to(ROOT / 'tests/cases'))[:-5]
             for pattern in PATTERNS for p in (ROOT / 'tests/cases').glob(pattern)}
    assert compare_facts(compiler, tmp_path, monkeypatch, sorted(found), leaves=LEAVES) > 100
