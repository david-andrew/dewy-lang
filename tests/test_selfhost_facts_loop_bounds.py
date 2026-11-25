"""Loop-bound preparation, demand order and speculative proofs match frozen Jo."""
import pytest
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAF = ('facts_loops',)
DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'effect_types.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'expr.jo'
use 'facts.jo'
use 'facts_index_writes.dewy'
use 'facts_value_queries.dewy'
use 'facts_projection_queries.dewy'
use 'refinement_types.dewy'
main = ():
    init_types()
    nodes = fill(Node(), 128); locals = fill(Local(), 8)
    arr = types.len(); types.push(TypeInfo(kind=.array, elem=i32(T_INT)))
    locals[1] = Local(owner=1, type=i32(T_INT), pos=10)
    locals[2] = Local(owner=1, type=i32(arr), pos=10)
    locals[3] = Local(owner=1, type=i32(T_INT), pos=10)
    locals[4] = Local(owner=1, type=i32(T_INT), pos=10)
    nodes[1] = Node(kind=.ident, aux=i32(int(SK.local)), sym=2, type=i32(arr))
    nodes[2] = Node(kind=.ident, aux=i32(int(SK.local)), sym=1, type=i32(T_INT))
    nodes[3] = Node(kind=.conv, a=2, type=i32(T_INT))
    nodes[4] = Node(kind=.index, a=1, b=3, type=i32(T_INT), pos=150)
    if fact_loop_index_local(4) != 1: exit(11)
    nodes[2].aux = i32(int(SK.global))
    if fact_loop_index_local(4) != 0: exit(12)
    nodes[2].aux = i32(int(SK.local)); nodes[1].aux = i32(int(SK.global))
    if fact_loop_index_local(4) != 0: exit(13)
    nodes[1].aux = i32(int(SK.local)); nodes[1].type = i32(T_INT)
    if fact_loop_index_local(4) != 0: exit(14)
    nodes[1].type = i32(arr)
    # Both operand sides and wrapped local identities retain step recognition.
    nodes[8] = Node(kind=.int_lit, ival=1, type=i32(T_INT))
    nodes[9] = Node(kind=.binary, a=8, b=3, op=i32(int(Tok.plus)))
    nodes[10] = Node(kind=.conv, a=9)
    if not fact_loop_step(10, 1) or fact_loop_step(10, 2) or fact_loop_step(0, 1): exit(15)
    nodes[9].op = i32(int(Tok.minus)); nodes[9].a = 3; nodes[9].b = 8
    if not fact_loop_step(10, 1): exit(16)
    nodes[9].op = i32(int(Tok.star))
    if fact_loop_step(10, 1): exit(17)
    # Record fields with a storage contract cannot seed an unbounded step.
    si = structs.len(); st = types.len(); fi = fields.len()
    fields.push(Field(type=i32(T_INT))); structs.push(StructInfo(fields=i32(fi), nfields=1, resolved=true))
    types.push(TypeInfo(kind=.struct_, st=i32(si)))
    nodes[6] = Node(kind=.ident, type=i32(st))
    nodes[7] = Node(kind=.field, a=6, type=i32(T_INT))
    nodes[11] = Node(kind=.conv, a=7)
    if not fact_loop_unbounded_field(11) or fact_loop_unbounded_field(0): exit(18)
    fields[fi].type = i32(T_I8)
    if fact_loop_unbounded_field(11): exit(19)
    # Demand filtering preserves duplicates, source order, four-entry cap and
    # lazy carried-assignment discovery. Only active/member marks matter.
    nodes[20] = Node(kind=.for_, a=1, b=30, sym=3, c=4, pos=100)
    nodes[30] = Node(kind=.block)
    nodes[31] = Node(kind=.assign, a=2, b=8)
    fact_slice = FactSlice(base=0, flags=fill(0, 128))
    fact_carried_cache.clear()
    if fact_loop_bound_demands(20).len() != 0 or fact_carried_cache.has(20): exit(20)
    fact_slice.loop_indexes = [4, 4, 4, 4, 4]
    fact_carried_cache[20] = [31]
    demand_snapshot = fact_slice.loop_indexes
    got = fact_loop_bound_demands(20)
    if got.len() != 4 or demand_snapshot.len() != 5: exit(21)
    loop m in got:
        if m != 4: exit(22)
    fact_slice.flags[31] = FACT_MEMBER
    if fact_loop_bound_demands(20).len() != 0: exit(23)
    fact_slice.flags[31] |= FACT_ACTIVE
    if fact_loop_bound_demands(20).len() != 4: exit(24)
    nodes[4].pos = 90
    if fact_loop_bound_demands(20).len() != 0: exit(25)
    nodes[4].pos = 150; locals[1].pos = 100
    if fact_loop_bound_demands(20).len() != 0: exit(26)
    locals[1].pos = 10; fact_slice = FactSlice()
    # Terms may grow projections; retained state and positional identities
    # survive that growth. Assumptions retain interval and relational order.
    fact_terms = [FactTerm()]; s = FactState()
    av = fact_new(s, FactBound(), FactTerm(type=arr))
    xv = fact_new(s, FactBound(-1, 20), FactTerm(type=T_INT))
    fact_bind(s, PlaceIdentity(.local, 1, 2), av)
    fact_bind(s, PlaceIdentity(.local, 1, 1), xv)
    old = s
    terms = fact_loop_bound_terms(s, 4)
    if terms.0 != xv or terms.1 == 0 or old.projections.len() != 0: exit(30)
    if fact_loop_bound_holds(s, 4): exit(31)
    fact_set_bound(s, terms.1, FactBound(4, 10))
    before = s
    fact_loop_bound_assume(s, 4, 20)
    b = fact_bound(s, xv)
    if b.lo != 0 or b.hi != 9 or fact_bound(before, xv).lo != -1 or not fact_loop_bound_holds(s, 4): exit(32)
    got = fact_loop_bound_entry([4, 4], s)
    if got.len() != 2: exit(33)
    dead = FactState(live=false)
    if not fact_loop_bound_holds(dead, 4) or fact_loop_bound_entry([4], dead).len() != 0: exit(34)
    empty = FactState()
    if fact_loop_bound_terms(empty, 4).0 != 0: exit(35)
    # A failed candidate is dropped, then survivors are rechecked from the
    # original head. Nested attempts preserve the enclosing budget; top-level
    # attempts restore it, including on exhaustion.
    nodes[5] = Node(kind=.index, a=1, b=12, type=i32(T_INT))
    nodes[12] = Node(kind=.ident, aux=i32(int(SK.local)), sym=3, type=i32(T_INT))
    nodes[60] = Node(kind=.bool_lit, ival=1, type=i32(T_BOOL))
    nodes[20].a = 60
    fact_speculating = 0; fact_loop_steps = 17; fact_loop_exhausted = false
    fact_summary_owner = 0; fact_constructor_budget = -1; fact_step_limit = 10000
    retained = s
    if not fact_loop_bounds(20, s, [5, 4], FACT_PREP_CONDITION, 0, 0, 0, []): exit(40)
    if fact_speculating != 0 or fact_loop_steps != 17 or fact_loop_exhausted or retained.ids.len() > s.ids.len(): exit(41)
    if fact_loop_bounds(20, s, [5], FACT_PREP_CAPTURE, 0, 0, 0, []): exit(42)
    fact_speculating = 2; fact_loop_steps = 0
    if not fact_loop_bounds(20, s, [4], FACT_PREP_CAPTURE, 0, 0, 0, []) or fact_speculating != 2 or fact_loop_steps == 0: exit(43)
    fact_loop_steps = 0; fact_step_limit = 0
    if fact_loop_bounds(20, s, [4], FACT_PREP_CAPTURE, 0, 0, 0, []) or not fact_loop_exhausted or fact_speculating != 2: exit(44)
    fact_loop_exhausted = false; fact_speculating = 0; fact_loop_steps = 0
    if fact_loop_bounds(20, s, [4], FACT_PREP_CAPTURE, 0, 0, 0, []) or fact_loop_exhausted or fact_loop_steps != 0: exit(45)
    fact_step_limit = 10000; fact_summary_owner = 1
    if fact_loop_bounds(20, s, [4], FACT_PREP_CAPTURE, 0, 0, 0, []): exit(46)
    fact_summary_owner = 0; fact_loop_exhausted = true
    if fact_loop_bounds(20, s, [4], FACT_PREP_CAPTURE, 0, 0, 0, []): exit(47)
    fact_loop_exhausted = false
    # Indexed preparation binds a fresh position below the existing length.
    nodes[20].a = 1
    fact_loop_prepare(20, s, FACT_PREP_INDEXED, av, [])
    i = fact_binding(s, PlaceIdentity(.local, 1, 4))
    if i < 0 or fact_bound(s, s.bindings[i].value).lo != 0: exit(48)
    print("loop-bound facts ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_facts_loop_bounds_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)


def test_facts_loop_bounds_program_twins(compiler, tmp_path, monkeypatch):
    cases = sorted(str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                   for p in (ROOT / 'tests/cases/loop_bounds').glob('*.dewy'))
    cases += ['facts/loop_guard', 'sequence/slice_loop_bounds_order',
              'sequence/slice_loop_bound_locals', 'tests/ladder/95_kv_store/design.dewy']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAF) >= 5
