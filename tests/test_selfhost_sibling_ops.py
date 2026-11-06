"""Sibling record literals: positions, arrays, known contents and followed bindings match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
const NF_CHECKED = 1
const NF_MUT = 2
const LF_SHARED = 1
const LF_ADDR = 2
const LF_CAPTURE = 4
const T_SHAPE = 1
const T_CIRCLE = 2
const T_SQUARE = 3
const T_DOT = 4
const T_OTHER = 5
const T_INT = 6
const T_CS = 7
const T_CI = 8
const T_TUPLE = 9
const T_TUPLE_BAD = 10
const T_BOTH = 11
struct Watch:
    sibling_known: int
    sibling_flow: int
nodes: Node[] = [Node()]
lists: i32[]
lists2: i32[]
locals: Local[] = [Local()]
syms: Sym[] = [Sym()]
ctxs: FnCtx[] = [FnCtx(inst=2, loop_depth=1)]
cx = 0
types: TypeInfo[] = [TypeInfo(), TypeInfo(kind=.struct_), TypeInfo(kind=.struct_), TypeInfo(kind=.struct_), TypeInfo(kind=.struct_), TypeInfo(kind=.struct_), TypeInfo(kind=.int_), TypeInfo(kind=.enum_), TypeInfo(kind=.enum_), TypeInfo(kind=.tuple, nargs=2), TypeInfo(kind=.tuple, nargs=2), TypeInfo(kind=.enum_)]
nominal_parent: {int: int} = {2: 1, 3: 1, 4: 2}
statement_watch = Watch(0, 0)
scope: {int: int} = {}
narrowed: {int: int} = {}
cur_assign = 0
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
set_kid = (n: int, i: int, v: int): lists[int(nodes[n].list) + i] = i32(v)
nkids = (n: int) -> int: int(nodes[n].nlist)
nkids2 = (n: int) -> int: int(nodes[n].nlist2)
kid_c = (n: int) -> int: int(nodes[n].c)
kid_d = (n: int) -> int: int(nodes[n].d)
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
kids2 = (n: int) -> int[]:
    out: int[]
    loop i in [0..nkids2(n)): out.push(int(lists2[int(nodes[n].list2) + i]))
    out
mk = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
add_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) | f)
dewy_at = (pos: int) -> bool: pos < 100000
lookup = (name: int) -> int: scope.get(name) ?? 0
check_expr = (n: int, e: int) -> int:
    print("check_expr {n} {e}")
    int(nodes[n].type)
check_stmt = (s: int): print("check_stmt {s}")
new_sym = (name: int, kind: SK, r: int, decl: int) -> int:
    syms.push(Sym(name=i32(name), kind=kind, ref=i32(r), decl=i32(decl)))
    print("new_sym {name} {r} {decl}")
    syms.len() - 1
push_scope_sym = (name: int, sym: int):
    print("push_scope_sym {name} {sym}")
    scope[name] = sym
narrow_local = (l: int, ts: int[], pos: int): print("narrow_local {l} {ts} {pos}")
narrow_invalidate = (l: int): print("narrow_invalidate {l}")
narrowed_var = (l: int) -> int: narrowed.get(l) ?? 0
ctx_dependent = (n: int) -> bool: nodes[n].kind == .lambda
is_lit = (n: int) -> bool: nodes[n].kind == .int_lit
ntype = (n: int) -> int: int(nodes[n].type)
coerce = (n: int, t: int) -> int:
    print("coerce {n} {t}")
    n
bc_int = (v: int, pos: int) -> int:
    n = mk(.int_lit, pos)
    nodes[n].ival = v
    n
mk_ident_local = (l: int, pos: int) -> int:
    n = mk(.ident, pos)
    nodes[n].sym = i32(l); nodes[n].aux = 1
    n
resolve_type = (tn: int) -> int: int(nodes[tn].name) - 100
prune = (t: int) -> int: t
tkind = (t: int) -> TK: types[t].kind
type_eq = (a: int, b: int) -> bool: a == b
targ = (t: int, i: int) -> int:
    if t == T_TUPLE_BAD and i == 1: return T_OTHER
    if i == 0: T_CIRCLE else: T_SQUARE
is_union = (t: int) -> bool: t == T_CS or t == T_CI or t == T_BOTH
union_members = (t: int) -> int[]:
    if t == T_CS: return [T_CIRCLE, T_SQUARE]
    if t == T_CI: return [T_CIRCLE, T_INT]
    [T_CIRCLE]
union_index = (t: int, m: int) -> int:
    loop i in 0.. and x in union_members(t):
        if x == m: return i
    -1
mk_union = (ms: int[]) -> int:
    print("mk_union {ms}")
    T_CS
mk_array = (t: int) -> int:
    print("mk_array {t}")
    types.push(TypeInfo(kind=.array, elem=i32(t)))
    types.len() - 1
mk_tuple = (ts: int[]) -> int:
    print("mk_tuple {ts}")
    T_TUPLE
dt = (t: int) -> str: "T{t}"
name_of = (n: int) -> str:
    if n == 1: return "push"
    "n{n}"
warn = (pos: int, msg: str): print("warn {pos}: {msg}")
'''

DRIVER = r'''
use 'sibling_types.jo'
typed = (k: NK, t: int) -> int:
    n = mk(k, nodes.len())
    nodes[n].type = i32(t)
    n
ident = (name: int) -> int:
    n = mk(.ident, 9)
    nodes[n].name = i32(name)
    n
local_ident = (l: int) -> int:
    n = mk(.ident, 9)
    nodes[n].aux = 1; nodes[n].sym = i32(l)
    n
block = (items: int[]) -> int:
    n = mk(.block, 3)
    set_list(n, items)
    n
assign = (op: Tok, a: int, b: int) -> int:
    n = mk(.assign, 4)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
field = (base: int, name: int) -> int:
    n = mk(.field, 5)
    nodes[n].a = i32(base); nodes[n].name = i32(name)
    n
call = (callee: int, args: int[]) -> int:
    n = mk(.call, 6)
    nodes[n].a = i32(callee)
    set_list(n, args)
    n
vardecl = (name: int, value: int) -> int:
    n = mk(.vardecl, 7)
    nodes[n].name = i32(name); nodes[n].b = i32(value)
    n
bind_local = (name: int, t: int) -> int:
    locals.push(Local(name=i32(name), type=i32(t)))
    syms.push(Sym(kind=.local, ref=i32(locals.len() - 1)))
    scope[name] = syms.len() - 1
    locals.len() - 1
list2 = (n: int, items: int[]):
    nodes[n].list2 = i32(lists2.len()); nodes[n].nlist2 = i32(items.len())
    loop x in items: lists2.push(i32(x))
literal = (t: int) -> int:
    callee = ident(100 + t)
    call(callee, [])
known_text = () -> str:
    keys = sibling_known.keys(); keys.sort()
    s = ""
    loop k in keys: s = "{s} {k}:{sibling_known[k].types}/{sibling_known[k].owner}/{sibling_known[k].depth}/{sibling_known[k].block != 0}"
    "{s} watch={statement_watch.sibling_known}"
in_block = (s: int, rest: int[]):
    sibling_block = block([s] + rest)
    sibling_index = 0
main = ():
    print("{sibling_descends(T_DOT, T_SHAPE)} {sibling_descends(T_CIRCLE, T_CIRCLE)} {sibling_descends(T_SQUARE, T_CIRCLE)} {sibling_descends(T_OTHER, T_SHAPE)}")
    # The family of a literal's elements.
    loop list in [[T_CIRCLE], [T_CIRCLE, T_CIRCLE], [T_CIRCLE, T_SQUARE], [T_DOT, T_SQUARE], [T_DOT, T_CIRCLE], [T_CIRCLE, T_OTHER], [T_CIRCLE, T_INT]]:
        items: int[]
        loop t in list: items.push(typed(.call, t))
        print("parent {sibling_parent(block(items))}")
    print(sibling_parent(block([typed(.int_lit, T_CIRCLE), typed(.call, T_SQUARE)])))
    # A literal's positions, then to an array.
    lit = block([typed(.call, T_CIRCLE), typed(.call, T_SQUARE)])
    print("{sibling_literal(lit)} {nodes[lit].kind == .tuple}")
    l0 = bind_local(20, T_TUPLE)
    print("{sibling_array_source(lit, T_TUPLE, T_SHAPE)} {sibling_array_source(lit, T_TUPLE, T_CS)} {sibling_array_source(lit, T_TUPLE, T_CIRCLE)} {sibling_array_source(lit, T_TUPLE_BAD, T_SHAPE)} {sibling_array_source(lit, T_TUPLE, T_CI)}")
    print("{sibling_array_source(local_ident(l0), T_TUPLE, T_SHAPE)} {sibling_array_source(typed(.call, 1), T_TUPLE, T_SHAPE)}")
    far = local_ident(l0); nodes[far].pos = 100001
    print(sibling_array_source(far, T_TUPLE, T_SHAPE))
    print("{sibling_to_array(lit, T_TUPLE, T_CS) == lit} {nodes[lit].kind == .array} {nodes[lit].type}")
    by_local = local_ident(l0)
    print("{sibling_to_array(by_local, T_TUPLE, T_CS) == by_local} {nodes[by_local].kind == .array} {nkids(by_local)}")
    loop item in kids(by_local): print("{nodes[item].kind == .index} {nodes[int(nodes[item].a)].sym} {nodes[int(nodes[item].b)].ival} {nodes[item].nlist}")
    # What may write a name.
    me = () -> int: ident(30)
    route = field(mk(.index, 1), 1); nodes[int(nodes[route].a)].a = i32(me())
    print("{sibling_route_name(me())} {sibling_route_name(route)} {sibling_route_name(0)} {sibling_route_name(mk(.call, 1))}")
    mutable = me(); nodes[mutable].flags = i32(NF_MUT)
    for_mut = mk(.for_, 1); nodes[for_mut].a = i32(me()); nodes[for_mut].flags = i32(NF_MUT)
    head_mut = mk(.lhead, 1); nodes[head_mut].a = i32(me()); nodes[head_mut].flags = i32(NF_MUT)
    for_plain = mk(.for_, 1); nodes[for_plain].a = i32(me())
    deep_c = mk(.if_, 1); nodes[deep_c].c = i32(assign(.assign, me(), mk(.int_lit, 1)))
    deep_d = mk(.if_, 1); nodes[deep_d].d = i32(assign(.assign, me(), mk(.int_lit, 1)))
    deep_a = mk(.if_, 1); nodes[deep_a].a = i32(assign(.assign, me(), mk(.int_lit, 1)))
    deep_b = mk(.if_, 1); nodes[deep_b].b = i32(assign(.assign, me(), mk(.int_lit, 1)))
    in_kids = block([assign(.assign, me(), mk(.int_lit, 1))])
    in2 = mk(.if_, 1); list2(in2, [assign(.assign, me(), mk(.int_lit, 1))])
    in2_lambda = mk(.lambda, 1); list2(in2_lambda, [assign(.assign, me(), mk(.int_lit, 1))])
    in2_fn = mk(.fn_, 1); list2(in2_fn, [assign(.assign, me(), mk(.int_lit, 1))])
    loop n in [0, me(), mutable, ident(31), assign(.assign, me(), mk(.int_lit, 1)), assign(.assign, ident(31), mk(.int_lit, 1)), call(field(me(), 1), []), call(field(ident(31), 1), []), call(me(), []), for_mut, head_mut, for_plain, deep_a, deep_b, deep_c, deep_d, in_kids, in2, in2_lambda, in2_fn]:
        print("writes {sibling_writes(n, 30)}")
    # A binding: unwritten stays positional; written becomes the elements' union.
    value = block([typed(.call, T_CIRCLE), typed(.call, T_SQUARE)])
    sibling_literal(value)
    s = vardecl(30, value)
    in_block(s, [ident(31)])
    print(sibling_binding(s, T_TUPLE))
    in_block(s, [assign(.assign, me(), mk(.int_lit, 1)), ident(31)])
    print("{sibling_binding(s, T_TUPLE)} {sibling_pending}")
    sibling_block = 0
    value2 = block([typed(.call, T_CIRCLE), typed(.call, T_CIRCLE)])
    sibling_literal(value2)
    s2 = vardecl(30, value2)
    print("{sibling_binding(s2, T_TUPLE)} {sibling_pending}")
    sibling_index = 4
    sibling_block = block([s])
    sibling_binding(s, T_TUPLE)
    # Known contents: established, forgotten, extended by a push.
    sibling_pending = []
    sibling_establish(40)
    print(known_text())
    sibling_block = block([])
    sibling_pending = [T_CIRCLE, T_SQUARE]
    x = bind_local(41, T_CS)
    sibling_establish(x)
    print("{known_text()} {sibling_pending.len()}")
    sibling_forget(99)
    sibling_extending = x
    sibling_forget(x)
    print(known_text())
    sibling_extending = 0
    b = sibling_block
    push_of = (name: int, arg: int) -> int:
        st = mk(.exprstmt, 1)
        nodes[st].a = i32(call(field(ident(name), 1), [arg]))
        st
    sibling_statement(mk(.call, 1), b)
    done = push_of(41, typed(.call, T_CIRCLE)); nodes[done].flags = i32(NF_CHECKED)
    sibling_statement(done, b)
    not_push = mk(.exprstmt, 1); nodes[not_push].a = i32(call(field(ident(41), 2), [typed(.call, T_CIRCLE)]))
    sibling_statement(not_push, b)
    two_args = mk(.exprstmt, 1); nodes[two_args].a = i32(call(field(ident(41), 1), [ident(1), ident(2)]))
    sibling_statement(two_args, b)
    not_call = mk(.exprstmt, 1); nodes[not_call].a = i32(ident(1))
    sibling_statement(not_call, b)
    no_field = mk(.exprstmt, 1); nodes[no_field].a = i32(call(ident(1), [ident(2)]))
    sibling_statement(no_field, b)
    on_field = mk(.exprstmt, 1); nodes[on_field].a = i32(call(field(field(ident(41), 3), 1), [ident(2)]))
    sibling_statement(on_field, b)
    sibling_statement(push_of(42, typed(.call, T_CIRCLE)), b)
    other_l = bind_local(43, T_CS)
    print(other_l)
    sibling_statement(push_of(43, typed(.call, T_CIRCLE)), b)
    print(known_text())
    sibling_statement(push_of(41, typed(.call, T_SQUARE)), b)
    print(known_text())
    sibling_statement(push_of(41, typed(.lambda, T_SQUARE)), b)
    print(known_text())
    restore = () -> int:
        sibling_known[x] = SiblingKnown(types=[T_CIRCLE], owner=2, depth=1, block=b)
        x
    restore()
    sibling_statement(push_of(41, typed(.int_lit, T_SQUARE)), b)
    print(known_text())
    restore()
    sibling_statement(push_of(41, typed(.call, T_INT)), b)
    print(known_text())
    restore()
    sibling_statement(push_of(41, typed(.call, T_CIRCLE)), b + 1)
    print(known_text())
    restore()
    ctxs[0].loop_depth = 2
    sibling_statement(push_of(41, typed(.call, T_CIRCLE)), b)
    print(known_text())
    ctxs[0].loop_depth = 1
    restore()
    ctxs[0].inst = 7
    sibling_statement(push_of(41, typed(.call, T_CIRCLE)), b)
    print(known_text())
    ctxs[0].inst = 2
    sibling_known[x] = SiblingKnown(types=fill(T_CIRCLE, 8), owner=2, depth=1, block=b)
    sibling_statement(push_of(41, typed(.call, T_CIRCLE)), b)
    print(known_text())
    # Narrowing an index.
    restore()
    sibling_known[x].types = [T_CIRCLE, T_SQUARE, T_OTHER]
    ix = (base: int, at: int) -> int:
        n = mk(.index, 11)
        nodes[n].a = i32(base); nodes[n].b = i32(at)
        n
    ilit = (v: int) -> int:
        n = mk(.int_lit, 12)
        nodes[n].ival = v
        n
    narrow = (n: int, t: int):
        print("narrow {sibling_index_narrow(n, t)} {nodes[n].kind == .narrow} {nodes[n].aux} {nodes[n].type} {nodes[n].flags}")
    narrow(ix(local_ident(x), ilit(0)), T_CS)
    narrow(ix(local_ident(x), ilit(1)), T_CS)
    narrow(ix(local_ident(x), ilit(2)), T_CS)
    narrow(ix(local_ident(x), ilit(3)), T_CS)
    narrow(ix(local_ident(x), ilit(-1)), T_CS)
    through = mk(.conv, 1); nodes[through].a = i32(ilit(1))
    narrow(ix(local_ident(x), through), T_CS)
    empty_conv = mk(.conv, 1)
    narrow(ix(local_ident(x), empty_conv), T_CS)
    narrow(ix(local_ident(x), ident(1)), T_CS)
    narrow(ix(local_ident(x), ilit(0)), T_CIRCLE)
    narrow(typed(.call, 1), T_CS)
    narrow(ix(ident(1), ilit(0)), T_CS)
    narrow(ix(local_ident(other_l), ilit(0)), T_CS)
    mut_ix = ix(local_ident(x), ilit(0)); nodes[mut_ix].flags = i32(NF_MUT)
    narrow(mut_ix, T_CS)
    cur_assign = 1
    narrow(ix(local_ident(x), ilit(0)), T_CS)
    cur_assign = 0
    loop f in [1, 2, 4]:
        locals[x].flags = i32(f)
        narrow(ix(local_ident(x), ilit(0)), T_CS)
    locals[x].flags = 0
    ctxs[0].loop_depth = 2
    narrow(ix(local_ident(x), ilit(0)), T_CS)
    ctxs[0].loop_depth = 1
    ctxs[0].inst = 7
    narrow(ix(local_ident(x), ilit(0)), T_CS)
    ctxs[0].inst = 2
    # Syntax types.
    syms.push(Sym(kind=.struct_, ref=i32(mk(.fn_, 1)))); scope[102] = syms.len() - 1
    syms.push(Sym(kind=.alias_, ref=i32(mk(.fn_, 1)))); scope[103] = syms.len() - 1
    syms.push(Sym(kind=.type_, ref=0)); scope[104] = syms.len() - 1
    syms.push(Sym(kind=.fns, ref=0)); scope[105] = syms.len() - 1
    generic = mk(.fn_, 1); list2(generic, [1])
    syms.push(Sym(kind=.struct_, ref=i32(generic))); scope[106] = syms.len() - 1
    syms.push(Sym(kind=.type_, ref=0)); scope[107] = syms.len() - 1
    tagged = ident(102); nodes[tagged].sval = 1
    indexed = mk(.index, 1); nodes[indexed].a = i32(ident(102))
    loop v in [0, mk(.int_lit, 1), literal(2), indexed, literal(3), literal(4), literal(5), literal(6), literal(7), literal(9), call(tagged, []), call(field(ident(1), 1), []), call(0, [])]:
        print("syntax {sibling_syntax_type(v)}")
    # Scanning a block for written literals.
    scan = (n: int, in_fn: bool):
        out: int[]
        escapes = false
        sibling_scalar_scan(n, 30, in_fn, mut out, mut escapes)
        print("scan {out} {escapes}")
    scan(0, false)
    scan(mutable, false)
    scan(assign(.assign, me(), literal(3)), false)
    scan(assign(.assign, me(), literal(3)), true)
    scan(assign(.pluseq, me(), literal(3)), false)
    scan(assign(.assign, ident(31), literal(3)), false)
    scan(assign(.assign, me(), mk(.int_lit, 1)), false)
    in_lambda = mk(.lambda, 1); nodes[in_lambda].b = i32(assign(.assign, me(), literal(3)))
    scan(in_lambda, false)
    in_fn = mk(.fn_, 1); list2(in_fn, [assign(.assign, me(), literal(3))])
    scan(in_fn, false)
    wide = mk(.if_, 1); nodes[wide].a = i32(assign(.assign, me(), literal(2))); nodes[wide].b = i32(assign(.assign, me(), literal(3))); nodes[wide].c = i32(assign(.assign, me(), literal(4))); nodes[wide].d = i32(assign(.assign, me(), literal(2)))
    set_list(wide, [assign(.assign, me(), literal(3))]); list2(wide, [assign(.assign, me(), literal(4))])
    scan(wide, false)
    print("{sibling_family(T_CIRCLE, T_SQUARE)} {sibling_family(T_DOT, T_SQUARE)} {sibling_family(T_OTHER, T_SQUARE)} {sibling_family(T_CIRCLE, T_OTHER)}")
    # A record binding written with siblings.
    flow = (): print("flow {sibling_flow_next} {sibling_flow_member}")
    d = vardecl(30, typed(.call, T_CIRCLE))
    sibling_block = 0
    print(sibling_scalar(d, T_CIRCLE))
    sibling_block = block([d]); sibling_index = 3
    print(sibling_scalar(d, T_CIRCLE))
    sibling_block = block([mk(.call, 1)]); sibling_index = 0
    print(sibling_scalar(d, T_CIRCLE))
    in_block(d, [])
    print(sibling_scalar(d, T_CIRCLE))
    in_block(d, [ident(1)])
    print(sibling_scalar(d, T_OTHER))
    print(sibling_scalar(d, T_CIRCLE))
    in_block(d, [assign(.assign, me(), literal(2)), assign(.assign, me(), literal(5))])
    print(sibling_scalar(d, T_CIRCLE))
    in_block(d, [assign(.assign, me(), literal(3)), assign(.assign, me(), literal(3))])
    print(sibling_scalar(d, T_CIRCLE))
    flow()
    sibling_flow_next = 0
    in_block(d, [assign(.assign, me(), literal(3)), assign(.assign, me(), literal(4)), mutable])
    print(sibling_scalar(d, T_CIRCLE))
    flow()
    # An annotated union.
    in_block(d, [ident(1)])
    print("{sibling_annotated(d, T_CIRCLE, T_CIRCLE)} {sibling_annotated(d, T_CS, T_OTHER)} {sibling_annotated(d, T_BOTH, T_CIRCLE)} {sibling_annotated(d, T_CI, T_CIRCLE)}")
    print(sibling_annotated(d, T_CS, T_SQUARE))
    flow()
    sibling_flow_next = 0
    sibling_block = 0
    print(sibling_annotated(d, T_CS, T_SQUARE))
    sibling_block = block([d]); sibling_index = 2
    print(sibling_annotated(d, T_CS, T_SQUARE))
    in_block(d, [mutable])
    print(sibling_annotated(d, T_CS, T_SQUARE))
    # Following through the flow.
    y = bind_local(50, T_CS)
    sibling_block = 91
    sibling_flow_member = T_CIRCLE
    sibling_flow_next = 1
    sibling_flow_start(y, 21)
    print("{sibling_flow_next} {sibling_flow[y]} {statement_watch.sibling_flow}")
    alias = bind_local(50, T_SQUARE)
    narrowed[alias] = y
    print("{sibling_root(alias)} {sibling_root(y)}")
    target = () -> int: local_ident(alias)
    sibling_flow_assign(assign(.pluseq, target(), typed(.call, T_SQUARE)), 0)
    sibling_flow_assign(assign(.assign, mk(.call, 1), typed(.call, T_SQUARE)), 0)
    sibling_flow_assign(assign(.assign, local_ident(other_l), typed(.call, T_SQUARE)), 0)
    sibling_flow_assign(assign(.assign, target(), typed(.call, T_SQUARE)), 0)
    sibling_flow_assign(assign(.assign, target(), typed(.call, T_CIRCLE)), 0)
    sibling_flow_assign(assign(.assign, local_ident(y), typed(.call, T_SQUARE)), 0)
    sibling_flow_assign(assign(.assign, target(), typed(.call, T_OTHER)), 0)
    sibling_flow_assign(assign(.assign, target(), typed(.call, T_CS)), T_CIRCLE)
    converted = mk(.conv, 1); nodes[converted].a = i32(typed(.call, T_CIRCLE))
    sibling_flow_assign(assign(.assign, target(), converted), 0)
    non_ident = assign(.assign, field(ident(1), 1), typed(.call, T_SQUARE))
    sibling_flow_assign(non_ident, 0)
    # Writes inside loops.
    lw = (n: int, in_loop: bool): print("loop writes {sibling_loop_writes(n, 30, in_loop)}")
    lw(0, false)
    lw(assign(.assign, me(), mk(.int_lit, 1)), false)
    lw(assign(.assign, me(), mk(.int_lit, 1)), true)
    loop k in [NK.while_, NK.for_, NK.loopx, NK.lhead, NK.if_]:
        w = mk(k, 1)
        nodes[w].b = i32(assign(.assign, me(), mk(.int_lit, 1)))
        lw(w, false)
    w2 = mk(.while_, 1); nodes[w2].a = i32(assign(.assign, me(), mk(.int_lit, 1)))
    lw(w2, false)
    w3 = mk(.while_, 1); nodes[w3].c = i32(assign(.assign, me(), mk(.int_lit, 1)))
    lw(w3, false)
    w4 = mk(.while_, 1); nodes[w4].d = i32(assign(.assign, me(), mk(.int_lit, 1)))
    lw(w4, false)
    w5 = mk(.while_, 1); set_list(w5, [assign(.assign, me(), mk(.int_lit, 1))])
    lw(w5, false)
    w6 = mk(.while_, 1); list2(w6, [assign(.assign, me(), mk(.int_lit, 1))])
    lw(w6, false)
    w7 = mk(.lambda, 1); list2(w7, [assign(.assign, me(), mk(.int_lit, 1))])
    lw(w7, true)
    w8 = mk(.fn_, 1); list2(w8, [assign(.assign, me(), mk(.int_lit, 1))])
    lw(w8, true)
    # A followed variable a loop writes.
    locals[y].name = 30
    in_loop = mk(.while_, 1); nodes[in_loop].b = i32(assign(.assign, me(), mk(.int_lit, 1)))
    sibling_flow_loops(ident(1))
    sibling_flow_loops(in_loop)
    syms.push(Sym(kind=.local, ref=i32(y))); scope[30] = syms.len() - 1
    sibling_flow_loops(in_loop)
    syms.push(Sym(kind=.global, ref=i32(y))); scope[30] = syms.len() - 1
    sibling_flow_loops(in_loop)
    syms.push(Sym(kind=.local, ref=i32(other_l))); scope[30] = syms.len() - 1
    sibling_flow_loops(in_loop)
    syms.push(Sym(kind=.local, ref=i32(alias))); scope[30] = syms.len() - 1
    sibling_flow_loops(in_loop)
    scope.remove(30)
    sibling_flow_loops(in_loop)
    # Ends.
    sibling_flow[other_l] = 92
    sibling_flow_end(91)
    print("{sibling_flow.keys()} {statement_watch.sibling_flow}")
    sibling_flow_end(92)
    print("{sibling_flow.len()} {statement_watch.sibling_flow}")
    print("sibling ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_sibling_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/sibling_types.jo').read_text()
    state = state[state.index('SIBLING_CAP = 8'):]
    output = compare_narrow(compiler, tmp_path, release,
                            ('checker_tokens', 'node_store', 'checker_types', 'checker_state', 'sibling_ops'), DRIVER,
                            doubles={'services.jo': SERVICES, 'sibling_types.jo': "use 'checker_state.dewy'\n" + state},
                            services=('ast', 'check', 'checker_call_queries', 'checker_expr', 'errors', 'expr', 'lex', 'types', 'util'))
    assert output.endswith(b'sibling ok\n')
    for text in (b'and later a T3', b'narrow 2 true', b'narrow_invalidate', b'mk_union'):
        assert text in output, text
