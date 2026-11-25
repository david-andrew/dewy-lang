"""Dependent field stores, length mutations, mutable authority and record conversions agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly

LEAVES = ('refine_rare',)
# Rejected mutations: SafePath representations and partial record authority.
CASES = [
    'decided_path_contracts/representation_alias',
    'decided_path_contracts/representation_element',
    'decided_path_contracts/representation_field',
    'decided_path_contracts/representation_place_alias',
    'dict_sibling/no_shrink_in_callee',
    'length_in_place/swap_dependent_record',
    'record_field_shape/lent_to_helper',
    'record_field_shape/selector_in_index',
    'sibling_length/no_shrink_in_callee',
]
# Field stores and length changes on dependent records and refined storage, paired runs,
# private candidates and structural record conversions.
PATTERNS = ('record_paired_fields/*.dewy', 'sibling_length/*.dewy', 'dict_sibling/*.dewy',
            'length_in_place/*.dewy', 'refine_dependent_alias/*.dewy', 'record_field_shape/*.dewy',
            'refinement_aggregates/*.dewy', 'self_length/runtime_*.dewy', 'self_length/grow*.dewy',
            'decided_path_contracts/*.dewy', 'conversion/*record*.dewy')


def test_refine_field_store_program_twins(compiler, tmp_path, monkeypatch):
    found = {str(p.relative_to(ROOT / 'tests/cases'))[:-5]
             for pattern in PATTERNS for p in (ROOT / 'tests/cases').glob(pattern)}
    assert compare_facts(compiler, tmp_path, monkeypatch, sorted(found | set(CASES)), leaves=LEAVES) > 100
