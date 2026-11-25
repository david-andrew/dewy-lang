"""Pointer casts, exposure, ownership and mutable actuals match frozen facts_forgets."""
import pytest
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAF = ('facts_forgets',)
DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'source_types.dewy'
use 'effect_types.dewy'
use 'expr.jo'
use 'types.jo'
use 'type_ops.dewy'
use 'facts.jo'
use 'facts_index_writes.dewy'
use 'facts_value_queries.dewy'
use 'refinement_types.dewy'
use 'places.jo'
use 'ownership.jo'
use 'util.jo'
main = ():
    init_types()
    nodes = fill(Node(), 100)
    locals = fill(Local(), 8)
    globals = fill(Global(), 4)
    fns = fill(FnInst(), 4)
    files = [SrcFile(is_dewy=true), SrcFile(is_dewy=false)]
    modules = [Module(file=0, init_fn=1), Module(file=1, init_fn=2)]
    fns[1] = FnInst(kind=FK_INIT, mod=0)
    fns[2] = FnInst(kind=FK_INIT, mod=1)
    arr = mk_array(T_INT)
    ptr = mk_ptr(T_INT)
    nodes[1] = Node(kind=.ident, type=i32(arr))
    nodes[2] = Node(kind=.cast, a=1, type=i32(ptr))
    if not fact_pointer_cast(2): exit(11)
    loop t in [T_STR, ptr]:
        nodes[1].type = i32(t)
        if not fact_pointer_cast(2): exit(12)
    nodes[1].type = i32(T_INT)
    if fact_pointer_cast(2): exit(13)
    nodes[1].type = i32(arr); nodes[2].type = i32(T_INT)
    if fact_pointer_cast(2): exit(14)
    nodes[2].type = i32(ptr); nodes[2].kind = .conv
    if fact_pointer_cast(2): exit(15)
    nodes[2].kind = .cast; nodes[2].a = 0
    if fact_pointer_cast(2): exit(16)
    # Closed initializer globals, foreign initializers, ordinary functions,
    # each exposure flag, and readonly declarations checked before owner guards.
    g = PlaceIdentity(.global, 0, 1)
    globals[1] = Global(type=i32(arr), mod=0)
    fact_owner = 1
    if fact_exposed(g): exit(20)
    globals[1].fn_accessed = true
    if not fact_exposed(g): exit(21)
    globals[1].fn_accessed = false; globals[1].fn_written = true
    if not fact_exposed(g): exit(22)
    globals[1].fn_written = false; globals[1].exposed = true
    if not fact_exposed(g): exit(23)
    globals[1].exposed = false; fact_owner = 2
    if not fact_exposed(g): exit(24)
    fact_owner = 3
    if not fact_exposed(g): exit(25)
    fact_owner = 0
    if not fact_exposed(g) or not fact_exposed(PlaceIdentity(.global, 0, 0)): exit(26)
    nodes[3] = Node(kind=.vardecl, flags=i32(NF_RDONLY))
    globals[1].decl = 3
    if fact_exposed(g): exit(27)
    globals[1].decl = 0
    # Lent arrays, ownership, conservative flags, Jo locals, snapshot captures,
    # readonly iteration aliases, locks and the exact disjoint-probe identity.
    p = PlaceIdentity(.local, 1, 1)
    locals[1] = Local(owner=1, type=i32(arr), flags=i32(LF_ADDR))
    if fact_exposed(p) or not fact_own_local(p): exit(30)
    loop flag in [LF_MUTPARAM, LF_SHARED, LF_CAPTURE, LF_BYREF, LF_EXPOSED]:
        locals[1].flags = i32(LF_ADDR | flag)
        if not fact_exposed(p) or fact_own_local(p): exit(31)
    locals[1].flags = i32(LF_ADDR | LF_PARAM)
    if fact_own_local(p): exit(32)
    locals[1].flags = i32(LF_ADDR); locals[1].owner = 2
    if not fact_exposed(p) or not fact_own_local(p): exit(33)
    locals[1].owner = 1; locals[1].flags = i32(LF_ADDR | LF_CAPTURED)
    if fact_exposed(p) or fact_own_local(p): exit(34)
    # A snapshot capture of an owner is still reachable through its place.
    osi = structs.len(); structs.push(StructInfo(name="Owner", decl=99))
    ot = types.len(); types.push(TypeInfo(kind=.struct_, st=i32(osi)))
    ownership_decls[99 * 4 + 1] = 1
    locals[1].type = i32(ot)
    if not fact_exposed(p): exit(42)
    locals[1].type = i32(arr)
    if fact_exposed(p): exit(43)
    ownership_decls.clear()
    locals[1].flags = i32(LF_BYREF | LF_VALUEITER)
    if fact_exposed(p): exit(35)
    locals[1].flags = i32(LF_BYREF); map_loop_values[1] = true
    if fact_exposed(p): exit(36)
    map_loop_values.clear()
    if not fact_exposed(p): exit(37)
    place_locked[1] = true
    if fact_exposed(p): exit(38)
    place_locked.clear()
    locals[1].flags = i32(LF_MUTPARAM); fact_owner = 1; fact_probe_disjoint = 1
    if fact_exposed(p): exit(39)
    fact_owner = 2
    if not fact_exposed(p): exit(40)
    fact_probe_disjoint = 0
    locals[1].flags = i32(LF_ADDR); locals[1].type = i32(T_INT)
    if fact_own_local(p) or fact_own_local(g) or fact_own_local(PlaceIdentity()): exit(41)
    # A map actual changes once per visit, preserving the first same-event
    # prior even for duplicate actuals. A retained state must not change.
    si = structs.len(); structs.push(StructInfo(name="Map"))
    mt = types.len(); types.push(TypeInfo(kind=.struct_, st=i32(si)))
    locals[1] = Local(owner=1, flags=i32(LF_ADDR), type=i32(mt))
    nodes[4] = Node(kind=.ident, aux=i32(int(SK.local)), sym=1, type=i32(mt))
    nodes[5] = Node(kind=.addr, a=4)
    nodes[6] = Node(kind=.conv, a=5)
    ft = mk_fn([mt, mt], T_INT, 3)
    nodes[7] = Node(kind=.ident, type=i32(ft))
    nodes[8] = Node(kind=.call, aux=1, a=7)
    set_list(8, [6, 4])
    fact_terms = [FactTerm()]
    s = FactState()
    old = fact_constant(s, 7)
    fact_bind(s, p, old)
    snapshot = s
    fact_forget_mutable_maps(8, s, false, 17, .write)
    if s.bindings[0].value == old or s.bindings[0].event != 17 or s.bindings[0].prior != old: exit(50)
    if snapshot.bindings[0].value != old or snapshot.ids.len() != 1 or s.ids.len() != 3: exit(51)
    latest = s.bindings[0].value
    fact_forget_mutable_maps(8, s, true)
    if s.bindings[0].value != latest: exit(52)
    fact_forget_mutable_maps(8, s, false, 18)
    if s.bindings[0].prior != latest or s.bindings[0].event != 18: exit(53)
    # Non-map lent locals are invalidated only by the lent branch, and exposed
    # locals are left to the general forget. Missing bindings remain absent.
    locals[1].type = i32(arr)
    latest = s.bindings[0].value
    fact_forget_mutable_maps(8, s)
    if s.bindings[0].value != latest: exit(54)
    fact_forget_mutable_maps(8, s, true)
    if s.bindings[0].value == latest or s.bindings[0].event != 8: exit(55)
    latest = s.bindings[0].value; locals[1].flags = i32(LF_EXPOSED)
    fact_forget_mutable_maps(8, s, true)
    if s.bindings[0].value != latest: exit(56)
    empty = FactState()
    locals[1].flags = i32(LF_ADDR)
    fact_forget_mutable_maps(8, empty, true)
    if empty.bindings.len() != 0 or empty.ids.len() != 0: exit(57)
    nodes[8].kind = .int_lit
    fact_forget_mutable_maps(8, s, true)
    if s.bindings[0].value != latest: exit(58)
    # The signed machine mask includes bit 62, but the existing 62-actual
    # cap visits bit 61 only. Duplicate actuals make the visit count visible.
    nodes[8] = Node(kind=.call, sym=3)
    set_list(8, fill(4, 63))
    nodes[9] = Node(kind=.fn_)
    parameters: int[] = []
    loop i in [0..63):
        nodes[10 + i] = Node(kind=.param, flags=if i >= 61: i32(NF_MUT) else: 0)
        parameters.push(10 + i)
    set_list(9, parameters)
    fns[3] = FnInst(decl=9, ptypes=fill(arr, 63))
    before = s.ids.len()
    fact_forget_mutable_maps(8, s, true, 19)
    if s.ids.len() != before + 1 or s.bindings[0].event != 19: exit(59)
    if snapshot.bindings[0].value != old or snapshot.ids.len() != 1: exit(60)
    print("exposure and ownership ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_facts_exposure_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)


def test_facts_exposure_program_twins(compiler, tmp_path, monkeypatch):
    globs = ('dictionary/*.dewy', 'data_readonly/*.dewy', 'closure/*.dewy', 'place_method/*.dewy', 'ownership/*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in globs for p in (ROOT / 'tests/cases').glob(glob)})
    cases += ['witness/pool_update_callee', 'witness/pool_entry_copy', 'compound/pool']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAF) > 60
