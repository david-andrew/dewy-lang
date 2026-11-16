"""Refinement projection/value transfers preserve bounds, ordered rows and snapshots."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

LEAVES = ('refine_transfers',)
DRIVER = '''use 'main.jo'
use 'refine.jo'
use 'refinement_types.dewy'
use 'facts.jo'
use 'facts_index_writes.dewy'
use 'facts_value_queries.dewy'
use 'facts_compare.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'intern.dewy'
new_type = (info: TypeInfo) -> int:
    id = types.len(); types.push(info); id
plain_ids = (ids: int[]) -> int: ids[0]
main = ():
    init_types()
    fact_terms = [FactTerm()]
    fact_query = false; fact_owner = 1; fact_hull_owner = -1
    ref_fact_holder = 0
    s = FactState(); empty = s
    arr = mk_array(T_INT)
    name = intern("items")
    at = fields.len(); fields.push(Field(name=i32(name), type=i32(arr)))
    si = structs.len(); structs.push(StructInfo(fields=i32(at), nfields=1))
    record = new_type(TypeInfo(kind=.struct_, st=i32(si)))
    root = fact_new(s, FactBound(), FactTerm(type=record))
    array = ref_project(RefTerm(path=[name]), root, s)
    assert(plain_ids([array]) == array and fact_terms[array].type == arr)
    length = ref_project(RefTerm(path=[name, -1]), root, s)
    assert(ref_project(RefTerm(path=[name, -1]), root, s) == length)
    assert(ref_project(RefTerm(path=[name + 1]), root, s) == 0)
    assert(ref_project(RefTerm(path=[name]), 0, s) == 0)
    assert(empty.ids.len() == 0 and empty.projections.len() == 0)
    fact_set_bound(s, length, FactBound(2, 7, true))
    biased = ref_value(RefTerm(path=[name, -1]), root, [], T_U64, s)
    b = fact_bound(s, biased)
    assert(b.lo == (2 xor FACT_MIN) and b.hi == (7 xor FACT_MIN) and b.nz)
    unsigned = ref_value(RefTerm(1, -1), 0, [], T_U64, s)
    assert(fact_bound(s, unsigned).lo == FACT_MAX)
    assert(ref_value(RefTerm(2, 1), 0, [root], T_INT, s) == 0)
    assert(ref_value(RefTerm(5, 0), 0, [root], T_INT, s) == root)
    ref_fact_holder = length
    assert(ref_value(RefTerm(6), 0, [], T_INT, s) == length)
    ref_fact_holder = 0
    value = fact_new(s, FactBound(-4, 8), FactTerm(type=T_INT))
    saved = s; rows = s.differences.len()
    shifted = ref_value(RefTerm(offset=3), value, [], T_INT, s)
    b = fact_bound(s, shifted)
    assert(b.lo == -1 and b.hi == 11)
    assert(s.differences[rows].a == shifted and s.differences[rows].b == value and s.differences[rows].limit == 3)
    assert(s.differences[rows + 1].a == value and s.differences[rows + 1].b == shifted and s.differences[rows + 1].limit == -3)
    assert(saved.differences.len() == rows and saved.ids.len() + 1 == s.ids.len())
    lower = ref_value(RefTerm(offset=-3), value, [], T_INT, s)
    assert(fact_bound(s, lower).lo == -7 and fact_bound(s, lower).hi == 5)
    edge = fact_new(s, FactBound(FACT_MAX - 2, FACT_MAX - 1), FactTerm(type=T_INT))
    overflow = ref_value(RefTerm(offset=3), edge, [], T_INT, s)
    assert(fact_bound(s, overflow).wide)
    edge = fact_new(s, FactBound(FACT_MIN + 1, FACT_MIN + 2), FactTerm(type=T_INT))
    overflow = ref_value(RefTerm(offset=-3), edge, [], T_INT, s)
    assert(fact_bound(s, overflow).wide)
    ref_predicates = [[], [RefAtom(.le, RefTerm(1, -3), RefTerm()), RefAtom(.le, RefTerm(), RefTerm(1, 5))], [RefAtom(.lt, RefTerm(), RefTerm(6))]]
    scalar = new_type(TypeInfo(kind=.refined, elem=i32(T_INT), st=1))
    value = fact_new(s, FactBound(-10, 10), FactTerm(type=T_INT)); saved = s
    ref_assume(scalar, value, [], s)
    b = fact_bound(s, value); before = fact_bound(saved, value)
    assert(b.lo == -3 and b.hi == 5 and before.lo == -10 and before.hi == 10)
    stored = new_type(TypeInfo(kind=.refined, elem=i32(T_INT), st=2))
    value = fact_new(s, FactBound(-20, 20), FactTerm(type=T_INT))
    rows = s.ids.len(); ref_assume(stored, value, [], s)
    assert(s.ids.len() == rows and fact_bound(s, value).hi == 20)
    ref_fact_holder = fact_constant(s, 10)
    ref_assume(stored, value, [], s)
    assert(fact_bound(s, value).hi == 9)
    rows = s.ids.len(); ref_assume(T_INT, value, [], s)
    assert(s.ids.len() == rows)
    capped = FactState(full=true, ids=fill(1, FACT_CAP))
    assert(ref_value(RefTerm(1, 7), 0, [], T_INT, capped) == 0)
    print("refinement transfers preserve projections, bounds, rows and snapshots")
'''

@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_refine_transfers_state_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAVES)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAVES, jo_doubles=modules)


def test_refine_transfers_program_twins(compiler, tmp_path, monkeypatch):
    patterns = ('refinements/*.dewy', 'refine_proven_rows/*.dewy',
                'self_length/*.dewy', 'sibling_length/*.dewy', 'dict_sibling/*.dewy',
                'record_paired_fields/*.dewy', 'uint64_ceiling/*.dewy',
                'refine_length_helpers/*.dewy', 'nd_contracts/*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for pattern in patterns for p in (ROOT / 'tests/cases').glob(pattern)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAVES) > 50
