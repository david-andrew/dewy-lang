"""Reflexive keys and bounded dictionary transfers match frozen facts_maps."""
import pytest
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAF = ('facts_maps',)
DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'source_types.dewy'
use 'effect_types.dewy'
use 'expr.jo'
use 'types.jo'
use 'type_ops.dewy'
use 'facts.jo'
use 'facts_index_writes.dewy'
use 'facts_value_queries.dewy'
use 'facts_projection_queries.dewy'
use 'refinement_types.dewy'
use 'refine.jo'
use 'ownership.jo'
use 'util.jo'
record_type = (ts: int[]) -> int:
    si = structs.len(); ti = types.len(); first = fields.len()
    loop t in ts: fields.push(Field(type=i32(t)))
    structs.push(StructInfo(name="Key", fields=i32(first), nfields=i32(ts.len()), resolved=true))
    types.push(TypeInfo(kind=.struct_, st=i32(si)))
    value_hash_fns[ti] = 0; value_equal_fns[ti] = 0
    ti
main = ():
    init_types()
    nodes = fill(Node(), 128); locals = fill(Local(), 8); fns = fill(FnInst(), 8)
    fact_reflexive_keys.clear(); value_hash_fns.clear(); value_equal_fns.clear()
    if not fact_reflexive_key(T_INT) or not fact_reflexive_key(T_BOOL) or not fact_reflexive_key(T_STR) or fact_reflexive_key(T_FLOAT): exit(11)
    plain = record_type([T_INT, T_STR])
    if not fact_reflexive_key(plain) or fact_reflexive_key(plain, 5): exit(12)
    nested = record_type([plain])
    if fact_reflexive_key(nested, 4): exit(13)
    # A negative result persists until the Jo owner's reset, even if metadata
    # changes. The negative recursion guard also closes a synthetic type cycle.
    bad = record_type([T_FLOAT])
    if fact_reflexive_key(bad): exit(14)
    fields[int(structs[int(types[bad].st)].fields)].type = i32(T_INT)
    if fact_reflexive_key(bad): exit(15)
    held = fact_reflexive_keys
    fact_reflexive_keys.clear()
    if not fact_reflexive_key(bad) or (held.get(bad) ?? true): exit(16)
    cycle = record_type([T_INT])
    fields[int(structs[int(types[cycle].st)].fields)].type = i32(cycle)
    if fact_reflexive_key(cycle): exit(17)
    hashed = record_type([T_INT]); value_hash_fns[hashed] = 1
    if fact_reflexive_key(hashed): exit(18)
    unknown = record_type([T_INT]); value_equal_fns.clear()
    if fact_reflexive_key(unknown): exit(19)
    value_equal_fns[plain] = 0; value_equal_fns[bad] = 0
    snap = fact_reflexive_keys
    loop i in [0..80):
        t = record_type([T_INT])
        if not fact_reflexive_key(t): exit(20)
    if snap.len() + 80 != fact_reflexive_keys.len() or held.get(bad) != false: exit(21)
    # Equality accepts the same field of ordered parameters, not crossed
    # fields, assigned aliases or a different comparison.
    nodes[10] = Node(kind=.ident, sym=1)
    nodes[11] = Node(kind=.ident, sym=2)
    nodes[12] = Node(kind=.field, a=10, name=101, type=i32(T_INT))
    nodes[13] = Node(kind=.field, a=11, name=101, type=i32(T_INT))
    nodes[14] = Node(kind=.binary, a=12, b=13, op=i32(int(Tok.eq)))
    if not fact_reflexive_eq(14, 1, 2, 0): exit(30)
    nodes[13].name = 102
    if fact_reflexive_eq(14, 1, 2, 0): exit(31)
    nodes[13].name = 101; nodes[12].aux = -1
    if fact_reflexive_eq(14, 1, 2, 0): exit(32)
    nodes[12].aux = 0; nodes[14].op = i32(int(Tok.ne))
    if fact_reflexive_eq(14, 1, 2, 0): exit(33)
    nodes[14].op = i32(int(Tok.eq))
    nodes[15] = Node(kind=.ident, sym=1)
    nodes[16] = Node(kind=.vardecl, sym=3, b=15)
    nodes[17] = Node(kind=.ident, sym=2)
    nodes[18] = Node(kind=.vardecl, sym=4, b=17)
    nodes[10].sym = 3; nodes[11].sym = 4
    nodes[19] = Node(kind=.exprstmt, a=14)
    nodes[20] = Node(kind=.return_, a=19)
    nodes[21] = Node(kind=.block); set_list(21, [16, 18, 20])
    if not fact_reflexive_eq(21, 1, 2, 0): exit(34)
    locals[3].flags = i32(LF_ASSIGNED)
    if fact_reflexive_eq(21, 1, 2, 0): exit(35)
    locals[3].flags = 0; nodes[15].sym = 7
    if fact_reflexive_eq(21, 1, 2, 0): exit(36)
    nodes[15].sym = 1
    nodes[22] = Node(kind=.and_, a=14, b=14)
    if not fact_reflexive_eq(22, 3, 4, 0): exit(37)
    # Checked custom equality is demanded only when the record has two params.
    custom = record_type([T_INT]); value_equal_fns[custom] = 1
    fns[1] = FnInst(params=[1, 2], body=21)
    if not fact_reflexive_key(custom): exit(38)
    value_equal_fns[custom] = 2
    if not fact_reflexive_key(custom): exit(39)
    fact_reflexive_keys.clear(); fns[2] = FnInst(params=[1], body=21)
    if fact_reflexive_key(custom): exit(40)
    # Text equality must name a bundled function; a record call must name its
    # recorded equality. Cache hits and parameter aliases remain ordered.
    lib_dir = "/virtual/lib"; lib_root = "/virtual/lib/"
    files = [SrcFile(path="/virtual/lib/core/map.jo", is_dewy=true), SrcFile(path="/ordinary/user.dewy", is_dewy=true)]
    nodes[23] = Node(kind=.fn_, pos=1)
    fns[3] = FnInst(decl=23)
    nodes[24] = Node(kind=.call, sym=3); set_list(24, [12, 13])
    nodes[12].type = i32(T_STR); nodes[13].type = i32(T_STR)
    if not fact_reflexive_eq(24, 3, 4, 0): exit(41)
    nodes[23].pos = (1 << 40) + 1
    if fact_reflexive_eq(24, 3, 4, 0): exit(42)
    nodes[12].type = i32(plain); nodes[13].type = i32(plain)
    value_equal_fns[plain] = 3
    # plain's synthesized equality was already proven; this query uses its
    # cached key result and demands the exact recorded callee for the field.
    fact_reflexive_keys[plain] = true
    if not fact_reflexive_eq(24, 3, 4, 0): exit(43)
    nodes[24].sym = 2
    if fact_reflexive_eq(24, 3, 4, 0): exit(44)
    # Operation recognition: exact map path for clear, library provenance for
    # bounded reads, scalar/text keys, arity, direct calls, and owner exclusion.
    si = structs.len(); mt = types.len(); ta = type_args.len()
    type_args.push(i32(T_STR)); type_args.push(i32(T_INT))
    structs.push(StructInfo(name="Map", targs=i32(ta), ntargs=2, resolved=true))
    types.push(TypeInfo(kind=.struct_, st=i32(si)))
    locals[1] = Local(owner=1, type=i32(mt))
    nodes[30] = Node(kind=.ident, aux=i32(int(SK.local)), sym=1, type=i32(mt))
    nodes[31] = Node(kind=.addr, a=30, type=i32(mt))
    nodes[32] = Node(kind=.conv, a=31, type=i32(mt))
    nodes[33] = Node(kind=.fn_, pos=1, name=i32(intern("clear")))
    fns[4] = FnInst(decl=33)
    nodes[34] = Node(kind=.call, sym=4, type=i32(T_INT)); set_list(34, [32])
    fact_name_map_clear = 0; fact_name_pop = 0; fact_name_get = 0
    if not fact_map_clear_call(34) or fact_name_map_clear == 0: exit(50)
    files[0].path = "/virtual/lib/other.jo"
    if fact_map_clear_call(34): exit(51)
    files[0].path = "/virtual/lib/core/map.jo"
    set_list(34, [32, 30]); nodes[33].name = i32(intern("pop"))
    if fact_map_bounded_call(34) != 1: exit(52)
    set_list(34, [32, 30, 30])
    if fact_map_bounded_call(34) != 2: exit(53)
    nodes[33].name = i32(intern("get"))
    if fact_map_bounded_call(34) != 3: exit(54)
    set_list(34, [32, 30])
    if fact_map_bounded_call(34) != 0: exit(55)
    nodes[33].name = i32(intern("clear")); set_list(34, [32])
    type_args[ta] = i32(T_FLOAT)
    if fact_map_clear_call(34): exit(56)
    type_args[ta] = i32(T_STR); structs[si].decl = 33; ownership_decls[33 * 4 + 1] = 1
    if fact_map_clear_call(34): exit(57)
    ownership_decls.clear(); structs[si].decl = 0
    # Clear publishes zero length on a fresh value, retaining old snapshots.
    fact_terms = [FactTerm()]; s = FactState(); p = PlaceIdentity(.local, 1, 1)
    old = fact_new(s, FactBound(), FactTerm(type=mt)); fact_bind(s, p, old)
    before = s
    if not fact_map_clear(34, s): exit(60)
    fresh = s.bindings[0].value
    row = fact_projection_find(s, fresh, -1, false)
    if fresh == old or row < 0: exit(61)
    length = fact_bound(s, s.projections[row].value)
    if length.lo != 0 or length.hi != 0 or before.bindings[0].value != old or before.projections.len() != 0: exit(62)
    # Nonremoving get keeps storage; pop replaces it after creating the result.
    set_list(34, [32, 30, 30])
    result = fact_map_bounded(34, s, [0, 0, 0], 3)
    if result == 0 or s.bindings[0].value != fresh: exit(63)
    result = fact_map_bounded(34, s, [0, 0, 0], 2)
    if result == 0 or s.bindings[0].value == fresh or before.bindings[0].value != old: exit(64)
    # A rejected route still creates the bounded result first; clear does not.
    nodes[35] = Node(kind=.int_lit, type=i32(mt)); set_list(34, [35, 30, 30])
    count = s.ids.len()
    if fact_map_bounded(34, s, [0, 0, 0], 1) != 0 or s.ids.len() <= count: exit(65)
    print("bounded rejected-route values: {s.ids.len() - count}")
    count = s.ids.len()
    if fact_map_clear(34, s) or s.ids.len() < count: exit(66)
    print("clear rejected-route values: {s.ids.len() - count}")
    print("reflexive map facts ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_facts_map_queries_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)


def test_facts_map_queries_program_twins(compiler, tmp_path, monkeypatch):
    globs = ('dict_sibling/*.dewy', 'dictionary/*.dewy', 'dogfood38_proofs/record_keys*.dewy', 'dogfood38_followups/sorted_key_record_keys.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in globs for p in (ROOT / 'tests/cases').glob(glob)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAF) > 30
