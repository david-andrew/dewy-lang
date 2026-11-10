"""Type-derived sequences: fields and members loops, literals, record loops and names match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'evaluator_state.dewy'
use 'refinement_types.dewy'
const NF_CHECKED = 1
const NF_MUT = 2
const NF_U64 = 4
const T_INT = 1
const T_STR = 2
const T_SET = 3
const T_NUMS = 4
const T_MIXED = 5
const T_RECORD = 6
const T_MAP = 7
const T_ARRAY = 8
const T_FIXED = 9
const T_WIDE = 10
const T_GAPS = 11
const T_OPEN = 12
const T_TEXTVAL = 13
const T_MADE = 40
nodes: Node[] = [Node()]
lists: i32[]
globals: Global[] = [Global()]
syms: Sym[] = [Sym()]
name_table: {int: int} = {}
ct_values: CTValue[] = [CTValue()]
next_ct = 0
last_checked = 0
structs: StructInfo[] = [StructInfo(fields=1, nfields=2)]
fields: Field[] = [Field(), Field(name=71, type=1), Field(name=72, type=2)]
types: TypeInfo[] = [TypeInfo(), TypeInfo(kind=.int_), TypeInfo(kind=.str_), TypeInfo(kind=.enum_), TypeInfo(kind=.refined), TypeInfo(kind=.enum_), TypeInfo(kind=.struct_, st=0), TypeInfo(kind=.struct_, st=0), TypeInfo(kind=.array), TypeInfo(kind=.fixed), TypeInfo(kind=.refined), TypeInfo(kind=.refined), TypeInfo(kind=.refined), TypeInfo(kind=.str_)]
str_sets: str[][] = [[], ["z", "a"], ["q"]]
names: {str: int} = {"lambda": 1}
name_texts: str[] = ["", "lambda"]
dewy_pos_limit = 100000
scope_count = 0
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
kid_c = (n: int) -> int: int(nodes[n].c)
kid_d = (n: int) -> int: int(nodes[n].d)
mk = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
add_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) | f)
clone = (n: int) -> int:
    print("clone {n}")
    copy = nodes[n]
    nodes.push(copy)
    nodes.len() - 1
check_block = (b: int, e: int, v: bool): print("check_block {nodes[b].kind == .block} {nkids(b)} {e} {v}")
check_struct_fields = (si: int): print("check_struct_fields {si}")
cur_mod = () -> int: 8
dewy_at = (pos: int) -> bool: pos < dewy_pos_limit
new_sym = (name: int, kind: SK, r: int, decl: int) -> int:
    syms.push(Sym(name=i32(name), kind=kind, ref=i32(r), decl=i32(decl)))
    print("new_sym {name} {r} {decl}")
    syms.len() - 1
push_scope_sym = (name: int, sym: int):
    print("push_scope_sym {name} {sym}")
    name_table[name] = sym
    scope_count += 1
resolve_type = (n: int) -> int: int(nodes[n].type)
scope_mark = () -> int: scope_count
scope_reset = (mark: int):
    print("scope_reset {mark}")
    scope_count = mark
check_expr = (n: int, e: int) -> int:
    print("check_expr {n != 0} {e} {nodes[n].kind == .array}")
    last_checked = n
    if nodes[n].kind == .array: return T_ARRAY
    int(nodes[n].type)
lookup = (name: int) -> int: name_table.get(name) ?? 0
ct_literal = (item: int, pos: int) -> int:
    print("ct_literal {item} {pos}")
    mk(.int_lit, pos)
ct_run = (n: int) -> int:
    print("ct_run {n != 0}")
    next_ct
bc_str = (s: str, pos: int) -> int:
    n = mk(.str_lit, pos)
    nodes[n].sval = i32(intern(s))
    n
bc_int = (v: int, pos: int) -> int:
    n = mk(.int_lit, pos)
    nodes[n].ival = v
    n
bc_ident = (s: str, pos: int) -> int:
    n = mk(.ident, pos)
    nodes[n].name = i32(intern(s))
    n
bc_bin = (op: Tok, a: int, b: int, pos: int) -> int:
    n = mk(.binary, pos)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
bc_block = (items: int[], pos: int) -> int:
    # (making a node can move the arena under a caller's chosen destination)
    loop nodes.len() % 4096 != 0: nodes.push(Node())
    nodes.push(Node())
    n = mk(.block, pos)
    set_list(n, items)
    n
bc_if = (c: int, yes: int[], no: int[], pos: int) -> int:
    n = mk(.if_, pos)
    nodes[n].a = i32(c)
    nodes[n].b = i32(bc_block(yes, pos))
    n
coerce = (n: int, t: int) -> int:
    print("coerce {t}")
    n
expr_as_type = (e: int) -> int:
    print("expr_as_type {e != 0}")
    int(nodes[e].type)
finalize_literal = (n: int) -> int:
    print("finalize {n != 0}")
    n
int_intervals = (t: int) -> (bool, int[]):
    if t == T_NUMS: return (true, [1, 2, 7, 7])
    if t == T_WIDE: return (true, [0, 100])
    if t == T_GAPS: return (true, fill(0, 66))
    if t == T_INT: return (true, [1, 1])
    (false, [])
is_map_type = (t: int) -> bool: t == T_MAP
ntype = (n: int) -> int: int(nodes[n].type)
small_span = (a: int, b: int, cap: int) -> bool: b - a < cap
# (the stubbed unions hold literals: no alternative types)
type_alternatives = (u: int) -> int[]:
    out: int[]
    out
member_prepare = (scopes: int[], body: int):
    print("member_prepare {scopes.len()} {body != 0}")
member_scopes: {int: int} = {}
mk_refined = (t: int, id: int) -> int:
    print("mk_refined {t} {id}")
    T_MADE + id
ref_intern = (atoms: RefAtom[]) -> int:
    s = ""
    loop a in atoms: s = "{s} {int(a.op)}:{a.a.kind}:{a.a.value}:{a.b.kind}:{a.b.value}"
    print("ref_intern{s}")
    atoms.len()
str_set_of = (t: int) -> int: if t == T_SET: 1 else if t == T_TEXTVAL: 2 else: 0
str_set_type = (texts: str[]) -> int:
    print("str_set_type {texts}")
    T_SET
string_domain_members = (e: int) -> bool:
    print("string_domain_members")
    nkids(e) == 2
dt = (t: int) -> str: "T{t}"
is_union = (t: int) -> bool: t == T_MIXED
union_members = (t: int) -> int[]: [T_SET, T_NUMS, T_TEXTVAL]
mk_array = (t: int) -> int:
    print("mk_array {t}")
    T_ARRAY
mk_typeval = (t: int) -> int: 300 + t
mk_union = (ms: int[]) -> int:
    print("mk_union {ms}")
    T_MIXED
prune = (t: int) -> int: t
tkind = (t: int) -> TK: types[t].kind
fatal = (pos: int, msg: str): 
    print("fatal {pos}: {msg}")
    exit(3)
intern = (s: str) -> int:
    if let id = names.get(s): return id
    name_texts.push(s)
    names[s] = name_texts.len() - 1
    names[s]
name_of = (n: int) -> str: name_texts[n]
'''

DRIVER = r'''
use 'reflection.jo'
named = (text: str) -> int:
    n = mk(.ident, 9)
    nodes[n].name = i32(intern(text))
    n
call_of = (callee: int, args: int[]) -> int:
    n = mk(.call, 10)
    nodes[n].a = i32(callee)
    set_list(n, args)
    n
tname = (t: int) -> int:
    n = mk(.tname, 11)
    nodes[n].type = i32(t)
    n
members_of = (t: int) -> int: call_of(named("members"), [tname(t)])
fields_of = (t: int) -> int: call_of(named("fields"), [tname(t)])
slit = (text: str) -> int:
    n = mk(.str_lit, 12)
    nodes[n].sval = i32(intern(text))
    n
ilit = (v: int) -> int:
    n = mk(.int_lit, 13)
    nodes[n].ival = v
    n
pipe = (a: int, b: int) -> int:
    n = mk(.binary, 14)
    nodes[n].op = i32(int(Tok.pipe)); nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
neg = (a: int) -> int:
    n = mk(.unary, 15)
    nodes[n].op = i32(int(Tok.minus)); nodes[n].a = i32(a)
    n
show_values = (values: int[], singles: int[]):
    s = ""
    loop v in values:
        if nodes[v].kind == .str_lit: s = "{s} '{name_of(int(nodes[v].sval))}'"
        else: s = "{s} {nodes[v].ival}"
    print("values{s} {singles}")
scope_text = (s: int) -> str: "{nodes[s].kind == .reflect_scope} name={nodes[s].name} a={nodes[s].a != 0} ival={nodes[s].ival} aux={nodes[s].aux} aux2={nodes[s].aux2}"
everything = ():
    # The source of a loop, and whether it's a fields or members call.
    plain = mk(.int_lit, 1)
    iter = call_of(named("__dewy_iter"), [plain])
    print("{reflect_source(iter) == plain} {reflect_source(plain) == plain} {reflect_source(call_of(named("__dewy_iter"), [])) != plain} {reflect_source(call_of(named("other"), [plain])) == plain}")
    print("{reflect_fields(plain)} {reflect_fields(fields_of(T_RECORD))} {reflect_fields(members_of(T_SET))} {reflect_fields(call_of(mk(.field, 1), []))} {id_fields != 0} {id_members != 0}")
    print("{reflect_members(plain)} {reflect_members(members_of(T_SET))} {reflect_members(fields_of(T_RECORD))}")
    far = members_of(T_SET); nodes[far].pos = 100001
    print(reflect_members(far))
    farf = fields_of(T_RECORD); nodes[farf].pos = 100001
    print(reflect_fields(farf))
    syms.push(Sym(kind=.fns)); name_table[intern("members")] = syms.len() - 1; name_table[intern("fields")] = syms.len() - 1
    print("{reflect_members(members_of(T_SET))} {reflect_fields(fields_of(T_RECORD))}")
    name_table.clear()
    print("{members_named(members_of(T_SET))} {members_named(fields_of(T_SET))}")
    # Literal members.
    loop t in [T_SET, T_NUMS, T_MIXED]:
        values: int[]
        singles: int[]
        literal_members(t, 7, mut values, mut singles)
        show_values(values, singles)
    # Leaves of an expression union.
    leaves = (e: int):
        texts: str[]
        ints: int[]
        others: int[]
        members_leaves(e, mut texts, mut ints, mut others)
        print("leaves {texts} {ints} {others}")
    leaves(pipe(pipe(slit("a"), slit("a")), pipe(ilit(1), pipe(ilit(1), pipe(neg(ilit(5)), neg(ilit(5)))))))
    opaque = mk(.call, 1); nodes[opaque].type = i32(T_SET)
    leaves(opaque)
    # Integer unions as a refined type.
    print(members_int_type([3, 1, 5], 3))
    print(members_int_type([2], 3))
    print(members_int_type([0, 25], 3))
    # A type from syntax.
    kinds = [NK.tname, NK.tunion, NK.trefined]
    loop k in kinds:
        n = mk(k, 1)
        nodes[n].type = i32(T_SET)
        print(members_type(n))
    print(members_type(tname(T_RECORD)))
    e0 = mk(.call, 1); nodes[e0].type = i32(T_NUMS)
    print(members_type(e0))
    print(members_type(slit("x")))
    print(members_type(ilit(1)))
    print(members_type(neg(ilit(1))))
    print(members_type(pipe(slit("x"), ilit(1))))
    print(members_type(pipe(pipe(slit("x"), ilit(1)), e0)))
    # The members array, a value.
    arr = members_of(T_SET)
    print("{members_literal(arr)} {nodes[arr].kind == .array} {nkids(arr)}")
    arr2 = members_of(T_NUMS)
    print("{members_array(arr2, 0)} {nkids(arr2)}")
    print(members_array(members_of(T_SET), T_ARRAY))
    print(members_array(members_of(T_SET), T_FIXED))
    print(members_array(members_of(T_SET), T_RECORD))
    # An argument.
    a1 = members_of(T_SET)
    members_argument(a1)
    print(nodes[a1].kind == .array)
    a2 = call_of(named("members"), [tname(T_SET), tname(T_SET)])
    members_argument(a2)
    print(nodes[a2].kind == .array)
    members_argument(plain)
    # Sequences.
    seq = (e: int, binder: int):
        out = reflect_sequence(e, binder)
        loop s in out: print(scope_text(s))
        print(out.len())
    seq(members_of(T_SET), 50)
    seq(call_of(named("__dewy_iter"), [members_of(T_NUMS)]), 51)
    seq(fields_of(T_RECORD), 52)
    values_of = mk(.call, 18); nodes[values_of].type = i32(T_ARRAY)
    ct_values.push(CTValue(items=[4, 5]))
    next_ct = ct_values.len() - 1
    seq(values_of, 53)
    fixed_of = mk(.call, 18); nodes[fixed_of].type = i32(T_FIXED)
    seq(fixed_of, 54)
    # Binding a scope.
    field_scope = reflect_sequence(fields_of(T_RECORD), 60)[0]
    reflect_bind(field_scope)
    value_scope = mk(.reflect_scope, 3); nodes[value_scope].name = 61; nodes[value_scope].a = i32(ilit(1)); nodes[nodes[value_scope].a].type = i32(T_INT)
    reflect_bind(value_scope)
    single_scope = mk(.reflect_scope, 3); nodes[single_scope].name = 62; nodes[single_scope].a = i32(ilit(1)); nodes[single_scope].aux2 = 55
    reflect_bind(single_scope)
    loop g in [globals.len() - 2, globals.len() - 1]: print("{globals[g].name} {globals[g].type} {globals[g].init != 0} {globals[g].mod} {globals[g].is_const} {globals[g].state}")
    # A computed field name.
    entry = (name_expr: int, value: int) -> int:
        n = mk(.pair, 20)
        nodes[n].b = i32(name_expr); nodes[n].a = i32(value)
        n
    plain_entry = entry(0, ilit(1))
    reflect_name(plain_entry)
    ct_values.push(CTValue(type=T_STR, s="computed"))
    next_ct = ct_values.len() - 1
    computed = entry(slit("x"), ilit(1))
    reflect_name(computed)
    print("{name_of(int(nodes[computed].name))} {nodes[computed].b}")
    # Members of a field descriptor.
    syms.push(Sym(kind=.reflected, ref=1)); name_table[intern("fd")] = syms.len() - 1
    syms.push(Sym(kind=.local, ref=1)); name_table[intern("loc")] = syms.len() - 1
    member = (receiver: int, name: str) -> int:
        n = mk(.field, 22)
        nodes[n].a = i32(receiver); nodes[n].name = i32(intern(name))
        n
    print(reflect_member(member(ilit(1), "name")))
    print(reflect_member(member(named("nothing"), "name")))
    print(reflect_member(member(named("loc"), "name")))
    m1 = member(named("fd"), "name")
    print("{reflect_member(m1)} {nodes[m1].kind == .str_lit} {nodes[m1].sval} {nodes[m1].type} {nodes[m1].flags} {last_checked == m1}")
    m2 = member(named("fd"), "type")
    print("{reflect_member(m2)} {nodes[m2].kind == .ident} {name_of(int(nodes[m2].name))} {nodes[m2].type} {nodes[m2].flags}")
    # Jumps.
    wrap = (k: NK, child: int) -> int:
        n = mk(k, 1)
        nodes[n].a = i32(child)
        n
    print("{reflect_jumps(0)} {reflect_jumps(mk(.break_, 1))} {reflect_jumps(mk(.continue_, 1))} {reflect_jumps(wrap(.lambda, mk(.break_, 1)))} {reflect_jumps(wrap(.block, mk(.break_, 1)))} {reflect_jumps(wrap(.block, mk(.int_lit, 1)))}")
    slot = (i: int) -> int:
        n = mk(.if_, 1)
        if i == 1: nodes[n].b = i32(mk(.break_, 1))
        if i == 2: nodes[n].c = i32(mk(.break_, 1))
        if i == 3: nodes[n].d = i32(mk(.break_, 1))
        if i == 4: set_list(n, [mk(.int_lit, 1), mk(.continue_, 1)])
        n
    loop i in [0..5): print(reflect_jumps(slot(i)))
    # Loops.
    loop_of = (source: int, body: int) -> int:
        s = mk(.for_, 30)
        nodes[s].a = i32(source); nodes[s].b = i32(body)
        v = mk(.ident, 31); nodes[v].name = 77
        set_list(s, [v])
        s
    print(reflect_loop(loop_of(plain, mk(.block, 1))))
    two = call_of(named("members"), [tname(T_SET), tname(T_SET)])
    print(reflect_loop(loop_of(two, mk(.block, 1))))
    straight = loop_of(members_of(T_SET), mk(.block, 1))
    print("{reflect_loop(straight)} {nodes[straight].kind == .block} {nkids(straight)}")
    loop item in kids_of(straight): print("{nodes[item].b != 0} {nodes[item].name}")
    # (a replayed template's later copies share the body)
    shared_loop = loop_of(members_of(T_SET), mk(.block, 1))
    jump_body = mk(.block, 1); set_list(jump_body, [mk(.break_, 1)])
    jumpy = loop_of(fields_of(T_RECORD), jump_body)
    print("{reflect_loop(jumpy)} {nodes[jumpy].kind == .for_} {nkids(jumpy)} {nkids(int(nodes[jumpy].b))} {nodes[int(nodes[jumpy].a)].kind == .range} {nodes[int(nodes[int(nodes[jumpy].a)].b)].ival} {name_of(int(nodes[kid(jumpy, 0)].name)) == "$field_iteration{jumpy}"}")
    loop item in kids_of(int(nodes[jumpy].b)): print("{nodes[item].kind == .if_} {nodes[int(nodes[int(nodes[item].a)].a)].kind == .ident} {nodes[int(nodes[int(nodes[item].a)].b)].ival}")
    print(shared_loop != 0)
    # Record loops: entries through a nested loop, then the record.
    value = (v: int) -> int:
        n = ilit(v)
        nodes[n].type = i32(T_INT)
        n
    inner = entry(0, value(1))
    rl = mk(.record_loop, 40)
    nodes[rl].a = i32(fields_of(T_RECORD)); nodes[rl].b = i32(inner); nodes[rl].name = 80
    record = mk(.record_lit, 41)
    nodes[record].kind = .pair
    nodes[record].a = i32(value(2))
    reflect_record(record)
    print("{nodes[record].kind == .record_lit} {nkids(record)} {nodes[kid(record, 0)].flags}")
    print(reflect_active)
    entries: int[]
    reflect_entries(rl, mut entries)
    print("{entries.len()} {reflect_active}")
kids_of = (n: int) -> int[]:
    out: int[]
    loop i in [0..nkids(n)): out.push(kid(n, i))
    out
main = ():
    case = if args().len() > 1: args()[1] else: "all"
    if case == "all": everything()
    else: failing(case)
    print("{case} ok")
failing = (case: str):
    if case == "open":
        values: int[]
        singles: int[]
        literal_members(T_OPEN, 1, mut values, mut singles)
    if case == "wide":
        values: int[]
        singles: int[]
        literal_members(T_WIDE, 2, mut values, mut singles)
    if case == "gaps":
        values: int[]
        singles: int[]
        literal_members(T_GAPS, 3, mut values, mut singles)
    if case == "not refined":
        types[T_NUMS].kind = .int_
        values: int[]
        singles: int[]
        literal_members(T_NUMS, 4, mut values, mut singles)
    if case == "span": members_int_type([0, 26], 5)
    if case == "literal arity": members_literal(call_of(named("members"), []))
    if case == "sequence arity": reflect_sequence(call_of(named("members"), []), 1)
    if case == "fields arity": reflect_sequence(call_of(named("fields"), []), 1)
    if case == "not record": reflect_sequence(fields_of(T_INT), 1)
    if case == "map": reflect_sequence(fields_of(T_MAP), 1)
    if case == "not array":
        n = mk(.call, 6); nodes[n].type = i32(T_INT)
        reflect_sequence(n, 1)
    if case == "runtime name":
        ct_values.push(CTValue(type=T_INT))
        next_ct = ct_values.len() - 1
        n = mk(.pair, 7)
        nodes[n].b = i32(slit("x"))
        reflect_name(n)
    if case == "bad member":
        syms.push(Sym(kind=.reflected, ref=1)); name_table[intern("fd")] = syms.len() - 1
        n = mk(.field, 8)
        nodes[n].a = i32(named("fd")); nodes[n].name = i32(intern("size"))
        reflect_member(n)
    if case == "two binders":
        s = mk(.for_, 9)
        nodes[s].a = i32(fields_of(T_RECORD))
        reflect_loop(s)
    if case == "mutable":
        s = mk(.for_, 10)
        nodes[s].a = i32(fields_of(T_RECORD)); nodes[s].flags = i32(NF_MUT)
        set_list(s, [named("x")])
        reflect_loop(s)
'''

FAILS = (('open', b'needs a union of literals'), ('wide', b'needs a union of literals'), ('gaps', b'needs a union of literals'), ('not refined', b'needs a union of literals'), ('span', b'more than 24 missing'),
         ('literal arity', b'members(U) needs one type'), ('sequence arity', b'members(U) needs one type'), ('fields arity', b'fields(T) needs one record type'), ('not record', b'needs a record type, found T1'),
         ('map', b'needs a record type, found T7'), ('not array', b'a record loop needs'), ('runtime name', b'fixed at compile time'), ('bad member', b'not .size'), ('two binders', b'one immutable value'), ('mutable', b'one immutable value'))


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_reflect_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/reflection.jo').read_text()
    state = state[state.index('reflect_active = false'):]
    outputs = compare_narrow(compiler, tmp_path, release,
                             ('checker_tokens', 'node_store', 'checker_types', 'checker_state', 'evaluator_state', 'refinement_types', 'reflect_ops'), DRIVER,
                             doubles={'services.jo': SERVICES, 'reflection.jo': state},
                             invocations=(((), 0), *(((case,), 3) for case, _ in FAILS)),
                             services=('ast', 'check', 'checker_expr', 'comptime', 'expr', 'lex', 'member_admit', 'member_replay', 'refine', 'string_domains', 'string_domain_ops', 'types', 'util'))
    assert outputs[0].endswith(b'all ok\n')
    for output, (_, text) in zip(outputs[1:], FAILS):
        assert text in output, (text, output)
