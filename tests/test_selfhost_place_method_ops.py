"""Place-returning methods: taking, guards, releases, lock_all, scans and matches match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'source_types.dewy'
use 'place_methods.jo'
const NF_ALIASDECL = 1
const NF_AT = 2
const NF_GLOBAL = 4
const NF_LITERAL = 8
const NF_LOOPCOUNT = 16
const NF_MUT = 32
const NF_RDONLY = 64
const NF_STMT = 128
const AUX2_PLACE = -11
const T_VOID = 1
const T_INT = 2
const T_MUTEX = 3
const T_TEXT = 4
nodes: Node[] = [Node()]
lists: i32[]
locals: Local[] = [Local()]
fns: FnInst[] = [FnInst()]
syms: Sym[] = [Sym()]
ctxs: FnCtx[] = [FnCtx(inst=2)]
cx = 0
types: TypeInfo[] = [TypeInfo(), TypeInfo(kind=.void_), TypeInfo(kind=.int_), TypeInfo(kind=.struct_, st=0), TypeInfo(kind=.str_)]
structs: StructInfo[] = [StructInfo(decl=0)]
fields: Field[]
check_struct_fields = (si: int): pass
fn_name_for = (t: int, name: int) -> bool: false
files: SrcFile[] = [SrcFile(path="a.dewy"), SrcFile(path="lib/prelude/locks.dewy")]
lib_dir = "lib"
deadlock_fns: {int: bool} = {}
place_locked: {int: bool} = {}
sibling_block = 0
sibling_index = 0
name_table: {int: int} = {}
names: {str: int} = {"lambda": 1}
name_texts: str[] = ["", "lambda"]
call_decl_of: {str: int} = {}
storage_type = 2
terminating: {int: bool} = {}
expr_type = 2
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
set_kid = (n: int, i: int, v: int): lists[int(nodes[n].list) + i] = i32(v)
nkids = (n: int) -> int: int(nodes[n].nlist)
kid_c = (n: int) -> int: int(nodes[n].c)
kid_d = (n: int) -> int: int(nodes[n].d)
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
mk = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
add_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) | f)
clear_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) & ~f)
clone = (n: int) -> int:
    copy = nodes[n]
    nodes.push(copy)
    r = nodes.len() - 1
    if nodes[n].a != 0:
        a = clone(int(nodes[n].a))
        nodes[r].a = i32(a)
    if nkids(n) > 0:
        items: int[]
        loop i in [0..nkids(n)): items.push(clone(kid(n, i)))
        set_list(r, items)
    r
intern = (s: str) -> int:
    if let id = names.get(s): return id
    name_texts.push(s)
    names[s] = name_texts.len() - 1
    names[s]
name_of = (n: int) -> str: name_texts[n]
fatal = (pos: int, msg: str):
    print("fatal {pos}: {msg}")
    exit(3)
pos_file = (pos: int) -> int: if pos >= 1000: 1 else: 0
pos_in_lib = (pos: int) -> bool: pos >= 1000
check_block = (b: int, e: int, v: bool) -> int:
    print("check_block {nkids(b)} {e} {v}")
    e + 1000
check_stmt = (s: int): print("check_stmt {nodes[s].kind == .assign}")
check_vardecl = (d: int):
    print("check_vardecl {name_of(int(nodes[d].name))} {nodes[d].flags}")
    b = int(nodes[d].b)
    if b != 0 and nodes[b].kind == .call and nodes[int(nodes[b].a)].kind == .field:
        name = name_of(int(nodes[int(nodes[b].a)].name))
        if let decl = call_decl_of.get(name): place_call_decl = decl
    locals.push(Local(type=2))
    syms.push(Sym(kind=.local, ref=i32(locals.len() - 1)))
    name_table[int(nodes[d].name)] = syms.len() - 1
push_type_params = (decl: int, targs: int[]): print("push_type_params {decl} {targs}")
resolve_type = (n: int) -> int: int(nodes[n].type)
scope_mark = () -> int: 77
scope_reset = (mark: int): print("scope_reset {mark}")
stmt_terminates = (n: int) -> bool: terminating.has(n)
check_expr = (n: int, e: int) -> int:
    print("check_expr {e}")
    b = int(nodes[n].a)
    if nodes[n].kind == .call and b != 0 and nodes[b].kind == .field:
        name = name_of(int(nodes[b].name))
        if let decl = call_decl_of.get(name): place_call_decl = decl
    expr_type
lookup = (name: int) -> int: name_table.get(name) ?? 0
bc_ident = (s: str, pos: int) -> int:
    n = mk(.ident, pos)
    nodes[n].name = i32(intern(s))
    n
bc_block = (items: int[], pos: int) -> int:
    # (making a node can move the arena under a caller's chosen destination)
    loop nodes.len() % 4096 != 0: nodes.push(Node())
    nodes.push(Node())
    n = mk(.block, pos)
    set_list(n, items)
    n
bc_let = (s: str, v: int, pos: int) -> int:
    n = mk(.vardecl, pos)
    nodes[n].name = i32(intern(s)); nodes[n].b = i32(v)
    n
bc_stmt = (e: int, pos: int) -> int:
    n = mk(.exprstmt, pos)
    nodes[n].a = i32(e)
    n
bc_method = (recv: int, name: str, args: int[], pos: int) -> int:
    f = mk(.field, pos)
    nodes[f].a = i32(recv); nodes[f].name = i32(intern(name))
    n = mk(.call, pos)
    nodes[n].a = i32(f)
    set_list(n, args)
    n
mk_ident_local = (l: int, pos: int) -> int:
    n = mk(.ident, pos)
    nodes[n].sym = i32(l)
    n
refine_storage = (n: int, t: int) -> int: storage_type
dt = (t: int) -> str: "T{t}"
prune = (t: int) -> int: t
tkind = (t: int) -> TK: types[t].kind
type_eq = (a: int, b: int) -> bool: a == b
'''

DRIVER = r'''
use 'place_methods.jo'
ident = (text: str) -> int:
    n = mk(.ident, 9)
    nodes[n].name = i32(intern(text))
    n
member = (base: int, text: str) -> int:
    n = mk(.field, 10)
    nodes[n].a = i32(base); nodes[n].name = i32(intern(text))
    n
call = (callee: int, args: int[], aux2: int) -> int:
    n = mk(.call, 11)
    nodes[n].a = i32(callee); nodes[n].aux2 = i32(aux2)
    set_list(n, args)
    n
take = (recv: int, method: str, args: int[]) -> int: call(member(recv, method), args, AUX2_PLACE)
decl_of = (method: str, info: PlaceMethod) -> int:
    d = mk(.fn_, 1)
    nodes[d].name = i32(intern(method))
    place_methods[d] = info
    call_decl_of[method] = d
    d
let_of = (name: str, value: int) -> int:
    n = mk(.vardecl, 12)
    nodes[n].name = i32(intern(name)); nodes[n].b = i32(value)
    n
shape = (n: int) -> str:
    if n == 0: return "0"
    x = nodes[n]
    s = "{name_of(int(x.name))}"
    if x.kind == .block: s = "block"
    else if x.kind == .call: s = "call"
    else if x.kind == .vardecl: s = "let {name_of(int(x.name))}"
    else if x.kind == .exprstmt: s = "stmt"
    else if x.kind == .assign: s = "assign"
    out = "{s}/{x.aux}/{x.aux2}/{x.flags}"
    if x.a != 0: out = "{out}(a {shape(int(x.a))})"
    if x.b != 0: out = "{out}(b {shape(int(x.b))})"
    loop i in [0..nkids(n)): out = "{out} [{shape(kid(n, i))}]"
    out
everything = ():
    # Names used.
    wanted: {int: bool} = {}
    wanted[intern("x")] = true
    deep = mk(.if_, 1); nodes[deep].c = i32(ident("x"))
    deeper = mk(.if_, 1); nodes[deeper].d = i32(ident("x"))
    listed = mk(.block, 1); set_list(listed, [ident("y"), ident("x")])
    aslot = mk(.if_, 1); nodes[aslot].a = i32(ident("x"))
    bslot = mk(.if_, 1); nodes[bslot].b = i32(ident("x"))
    loop n in [0, ident("x"), ident("y"), deep, deeper, listed, aslot, bslot, mk(.block, 1)]: print(place_names_used(n, wanted) != 0)
    # What a call may be.
    plain = mk(.fn_, 1); nodes[plain].name = i32(intern("plain"))
    lends = decl_of("lock", PlaceMethod(route=[intern("v")], guards=1, release=intern("lock$release")))
    place_call_seen(call(ident("c"), [], 0), plain)
    place_call_seen(call(ident("c"), [], AUX2_PLACE_TAKEN), lends)
    print(place_call_decl == lends)
    # Roots and bases.
    idx = mk(.index, 1); nodes[idx].a = i32(member(ident("r"), "f"))
    print("{place_root_name(ident("r"))} {place_root_name(idx)} {place_root_name(mk(.call, 1))} {place_route_base(idx)} {place_route_base(mk(.call, 1))}")
    print("{place_lends(take(ident("r"), "lock", []), intern("r"))} {place_lends(take(idx, "lock", []), intern("r"))} {place_lends(take(ident("q"), "lock", []), intern("r"))} {place_lends(call(member(ident("r"), "m"), [], 0), intern("r"))} {place_lends(call(ident("r"), [], AUX2_PLACE), intern("r"))} {place_lends(ident("r"), intern("r"))}")
    parts = place_call_parts(take(ident("loc"), "lock", []))
    print("{nodes[parts.0].kind == .ident} {name_of(parts.1)}")
    syms.push(Sym(kind=.local)); name_table[intern("loc")] = syms.len() - 1
    print(place_call_parts(take(member(ident("loc"), "f"), "lock", [])).1 != 0)
    print(place_call_parts(take(idx, "lock", [])).1 != 0)
    # A member call, a receiver, a shared one, an alias.
    mc = place_member_call(take(ident("r"), "lock", [ident("a")]), "$recv", "lock$release", 21)
    print(shape(mc))
    expr_type = T_INT
    print(place_shared_receiver(ident("r")))
    expr_type = T_MUTEX
    d_other = mk(.fn_, 5); nodes[d_other].name = i32(intern("Other"))
    d_mutex = mk(.fn_, 5); nodes[d_mutex].name = i32(intern("Mutex"))
    d_lib = mk(.fn_, 2000); nodes[d_lib].name = i32(intern("Mutex"))
    loop d in [0, d_other, d_mutex, d_lib]:
        structs[0].decl = i32(d)
        print(place_shared_receiver(ident("r")))
    print(place_receiver(ident("r"), 22))
    print(shape(place_hidden[place_hidden.len() - 1]))
    structs[0].decl = 0
    expr_type = T_INT
    print(place_receiver(ident("r"), 23))
    print(shape(place_hidden[place_hidden.len() - 1]))
    place_hidden = []
    show_alias = (info: PlaceMethod):
        l = place_alias(intern("a"), "$recv1", info, 24)
        print("{l} {place_locked.has(l)} {locals.len()}")
    show_alias(PlaceMethod(route=[intern("v"), intern("w")]))
    show_alias(PlaceMethod(route=[intern("v")], at=5))
    show_alias(PlaceMethod(route=[intern("v")], at=2000))
    # A written place type.
    g = let_of("g", 0)
    written_decl = mk(.fn_, 1)
    fns.push(FnInst(decl=i32(written_decl), targs=[6]))
    inner_call = mk(.call, 1); nodes[inner_call].sym = i32(fns.len() - 1)
    conv = mk(.conv, 1); nodes[conv].a = i32(inner_call)
    nodes[g].b = i32(conv)
    w = mk(.tname, 1); nodes[w].type = i32(T_INT)
    place_written_check(PlaceMethod(), written_decl, g, 1, 25)
    locals.push(Local(type=2))
    place_written_check(PlaceMethod(written=w), written_decl, g, locals.len() - 1, 25)
    other_g = let_of("g", 0)
    place_written_check(PlaceMethod(written=w), written_decl, other_g, locals.len() - 1, 25)
    nodes[g].b = i32(inner_call)
    place_written_check(PlaceMethod(written=w), 12345, g, locals.len() - 1, 25)
    # A let: not one, then taken with a guard released at once, after its last use, or by the block.
    print(place_let_decl(let_of("a", 0)))
    print(place_let_decl(let_of("a", ident("x"))))
    print(place_let_decl(let_of("a", call(ident("c"), [], 0))))
    statement = (rest: (str) -> int[], method: str) -> int:
        s = let_of("a", take(ident("acct"), method, []))
        b = mk(.block, 1)
        set_list(b, [s] + rest("a"))
        sibling_block = b
        sibling_index = 0
        print(place_let_decl(s))
        print(shape(s))
        print(shape(b))
        s
    no_more = (a: str) -> int[]: []
    used = (a: str) -> int[]: [ident("z"), ident(a), ident("z")]
    used_last = (a: str) -> int[]: [ident("z"), ident(a)]
    redeclared = (a: str) -> int[]: [let_of(a, ident("z")), ident(a)]
    decl_of("noguard", PlaceMethod(route=[intern("v")]))
    locks = decl_of("lib_lock", PlaceMethod(route=[intern("v")], guards=1, release=intern("lock$release"), at=2000))
    nodes[locks].pos = 2000
    statement(no_more, "lock")
    statement(used, "lock")
    statement(used_last, "lock")
    statement(redeclared, "lock")
    statement(used, "noguard")
    statement(used, "lib_lock")
    print("{deadlock_fns.len()} {place_locked.len()} {place_count}")
    ending = ident("a")
    terminating[ending] = true
    final_stop = (a: str) -> int[]: [ident("z"), ending, ident("z")]
    statement(final_stop, "lock")
    # lock_all, wholly.
    print(lock_all_decl(let_of("a", 0)))
    print(lock_all_decl(let_of("a", ident("x"))))
    wrapped_plain = mk(.propagate, 1); nodes[wrapped_plain].a = i32(ident("x"))
    print(lock_all_decl(let_of("a", wrapped_plain)))
    print(lock_all_decl(let_of("a", call(ident("f"), [], AUX2_PLACE))))
    print(lock_all_decl(let_of("a", call(member(ident("f"), "lock_all"), [], AUX2_PLACE))))
    decl_of("__take", PlaceMethod(route=[intern("v")], guards=1, release=intern("__take$release")))
    all_of = (binds: int[], locks: int[]) -> int:
        s = let_of("", 0)
        p = mk(.propagate, 14)
        nodes[p].a = i32(call(ident("lock_all"), locks, AUX2_PLACE))
        nodes[s].b = i32(p)
        set_list(s, binds)
        s
    hole = mk(.hole, 1)
    all_decl = all_of([ident("a"), hole], [ident("m"), member(ident("n"), "f")])
    bb = mk(.block, 1)
    set_list(bb, [all_decl, ident("a")])
    sibling_block = bb
    sibling_index = 0
    print(place_let_decl(all_decl))
    print(shape(all_decl))
    # What may happen while a place is live.
    scan = (n: int, arg: bool, closure: bool):
        place_scan(n, intern("a"), intern("r"), arg, closure)
        print("scan ok")
    scan(0, false, false)
    scan(ident("a"), false, false)
    atarg = ident("a"); nodes[atarg].flags = i32(NF_AT)
    scan(atarg, true, false)
    call_arg = mk(.call, 1); nodes[call_arg].a = i32(ident("f")); set_list(call_arg, [atarg])
    scan(call_arg, false, false)
    named_arg = mk(.namedarg, 1); nodes[named_arg].a = i32(atarg)
    call_named = mk(.call, 1); nodes[call_named].a = i32(ident("f")); set_list(call_named, [named_arg])
    scan(call_named, false, false)
    assign_other = mk(.assign, 1); nodes[assign_other].a = i32(ident("q")); nodes[assign_other].b = i32(ident("z"))
    scan(assign_other, false, false)
    assign_field = mk(.assign, 1); nodes[assign_field].a = i32(member(ident("r"), "f"))
    scan(assign_field, false, false)
    no_lend = let_of("z", ident("r"))
    scan(no_lend, false, false)
    other_lend = let_of("z", take(ident("q"), "lock", []))
    scan(other_lend, false, false)
    no_root = let_of("z", take(ident("r"), "lock", []))
    place_scan(no_root, intern("a"), 0, false, false)
    place_scan(ident("r"), intern("a"), 0, false, false)
    slots = mk(.if_, 1); nodes[slots].a = i32(ident("z")); nodes[slots].b = i32(ident("z")); nodes[slots].c = i32(ident("z")); nodes[slots].d = i32(ident("z"))
    scan(slots, false, false)
    # Ranges.
    range_block = mk(.block, 1)
    set_list(range_block, [ident("s"), ident("z"), ident("a"), ident("z"), let_of("a", ident("z")), ident("a")])
    print(place_range(range_block, 0, intern("a"), 0, 1))
    print(place_range(range_block, 3, intern("a"), 0, 1))
    print(place_range(range_block, 5, intern("a"), 0, 1))
    # Match: a failing method, split, and every arm form.
    decl_of("try_lock", PlaceMethod(route=[intern("v")], fails=true, guards=1, release=intern("try_lock$release")))
    arm_of = (t: int, name: str, body: int) -> int:
        p = mk(.ptype, 31)
        if name != "": nodes[p].name = i32(intern(name))
        if t != 0:
            tn = mk(.tname, 32)
            nodes[tn].type = i32(t)
            nodes[p].a = i32(tn)
        a = mk(.arm, 33)
        set_list(a, [p])
        nodes[a].b = i32(body)
        a
    matched = (args: int[], body: int, flags: int, expected: int):
        arms = [arm_of(T_TEXT, "busy", ident("x")), arm_of(T_INT, "", ident("x")), arm_of(0, "n", ident("x")), arm_of(T_INT, "got", body)]
        m = mk(.match_, 34)
        nodes[m].a = i32(take(ident("r"), "try_lock", args))
        nodes[m].flags = i32(flags)
        set_list(m, arms)
        print(place_match(m, expected))
        print(shape(m))
    plain_arg = ident("p")
    at_arg = ident("q"); nodes[at_arg].flags = i32(NF_AT)
    lit_arg = ident("l"); nodes[lit_arg].flags = i32(NF_LITERAL)
    na = mk(.namedarg, 35); nodes[na].a = i32(ident("v"))
    matched([plain_arg, at_arg, lit_arg, na], ident("x"), NF_STMT, 0)
    in_block = mk(.block, 36); set_list(in_block, [ident("y")])
    matched([], in_block, 0, T_INT)
    decl_of("lib_try", PlaceMethod(route=[intern("v")], fails=true, at=2000))
    lib_m = mk(.match_, 34)
    nodes[lib_m].a = i32(take(ident("r"), "lib_try", []))
    set_list(lib_m, [arm_of(T_INT, "got", ident("x"))])
    print(place_match(lib_m, 0))
main = ():
    case = if args().len() > 1: args()[1] else: "all"
    if case == "all": everything()
    else: failing(case)
    print("{case} ok")
failing = (case: str):
    plain = mk(.fn_, 1); nodes[plain].name = i32(intern("plain"))
    lends = decl_of("lock", PlaceMethod(route=[intern("v")], guards=1, release=intern("lock$release")))
    trying = decl_of("try_lock", PlaceMethod(route=[intern("v")], fails=true))
    print("{plain != 0} {lends != 0} {trying != 0}")
    block_for = (s: int):
        b = mk(.block, 1)
        set_list(b, [s])
        sibling_block = b
        sibling_index = 0
    if case == "seen place": place_call_seen(call(ident("c"), [], AUX2_PLACE), plain)
    if case == "seen value": place_call_seen(call(ident("c"), [], AUX2_PLACE_TAKEN), plain)
    if case == "seen plain": place_call_seen(call(ident("c"), [], 0), lends)
    if case == "not method": place_call_parts(call(ident("c"), [], AUX2_PLACE))
    if case == "temporary": place_call_parts(take(mk(.call, 1), "lock", []))
    if case == "global":
        syms.push(Sym(kind=.global)); name_table[intern("gl")] = syms.len() - 1
        place_call_parts(take(ident("gl"), "lock", []))
    if case == "written":
        storage_type = T_TEXT
        w = mk(.tname, 1); nodes[w].type = i32(T_INT)
        locals.push(Local(type=2))
        place_written_check(PlaceMethod(written=w), 1, let_of("g", 0), locals.len() - 1, 2)
    if case == "typed let":
        s = let_of("a", take(ident("r"), "lock", []))
        nodes[s].a = 1
        place_let_decl(s)
    if case == "readonly let":
        s = let_of("a", take(ident("r"), "lock", []))
        nodes[s].flags = i32(NF_RDONLY)
        place_let_decl(s)
    if case == "not own statement":
        place_let_decl(let_of("a", take(ident("r"), "lock", [])))
    if case == "takes value":
        s = let_of("a", take(ident("r"), "plain", []))
        block_for(s)
        place_let_decl(s)
    if case == "takes failing":
        s = let_of("a", take(ident("r"), "try_lock", []))
        block_for(s)
        place_let_decl(s)
    all_of = (binds: int[], locks: int[]) -> int:
        s = let_of("", 0)
        p = mk(.propagate, 14)
        nodes[p].a = i32(call(ident("lock_all"), locks, AUX2_PLACE))
        nodes[s].b = i32(p)
        set_list(s, binds)
        s
    if case == "lock_all bare": lock_all_decl(let_of("a", call(ident("lock_all"), [], AUX2_PLACE)))
    if case == "lock_all nameless": lock_all_decl(all_of([], [ident("m")]))
    if case == "lock_all pattern": lock_all_decl(all_of([mk(.call, 1)], [ident("m")]))
    if case == "lock_all count": lock_all_decl(all_of([ident("a")], [ident("m"), ident("n")]))
    if case == "lock_all not own": lock_all_decl(all_of([ident("a")], [ident("m")]))
    if case == "lock_all temporary":
        s = all_of([ident("a")], [mk(.call, 1)])
        block_for(s)
        lock_all_decl(s)
    if case == "lock_all global":
        syms.push(Sym(kind=.global)); name_table[intern("gl")] = syms.len() - 1
        s = all_of([ident("a")], [ident("gl")])
        block_for(s)
        lock_all_decl(s)
    if case == "scan closure": place_scan(ident("a"), intern("a"), 0, false, true)
    if case == "scan keep":
        n = ident("a"); nodes[n].flags = i32(NF_AT)
        place_scan(n, intern("a"), 0, false, false)
    if case == "scan pass root":
        n = ident("r"); nodes[n].flags = i32(NF_AT)
        place_scan(n, intern("a"), intern("r"), true, false)
    if case == "scan replace":
        n = mk(.assign, 1); nodes[n].a = i32(ident("r"))
        place_scan(n, intern("a"), intern("r"), false, false)
    if case == "scan second lock": place_scan(let_of("z", take(ident("r"), "lock", [])), intern("a"), intern("r"), false, false)
    if case == "scan second other": place_scan(let_of("z", take(ident("r"), "peek", [])), intern("a"), intern("r"), false, false)
    if case == "scan lambda":
        n = mk(.lambda, 1); nodes[n].b = i32(ident("a"))
        place_scan(n, intern("a"), 0, false, false)
    match_on = (method: str, arms: int[]) -> int:
        m = mk(.match_, 34)
        nodes[m].a = i32(take(ident("r"), method, []))
        set_list(m, arms)
        m
    arm_of = (t: int) -> int:
        p = mk(.ptype, 31)
        nodes[p].name = i32(intern("got"))
        tn = mk(.tname, 32)
        nodes[tn].type = i32(t)
        nodes[p].a = i32(tn)
        a = mk(.arm, 33)
        set_list(a, [p])
        nodes[a].b = i32(ident("x"))
        a
    if case == "match value": place_match(match_on("plain", []), 0)
    if case == "match always": place_match(match_on("lock", []), 0)
    if case == "match no arm": place_match(match_on("try_lock", [arm_of(T_TEXT)]), 0)
    if case == "match two arms": place_match(match_on("try_lock", [arm_of(T_INT), arm_of(T_INT)]), 0)
'''

FAILS = (('seen place', b'takes the place a method returns as'), ('seen value', b'gives a value, not a place'), ('seen plain', b'lends a place inside'), ('not method', b'takes the place a method returns'),
         ('temporary', b'bind it first'), ('global', b'is a global'), ('written', b'the place is written as'), ('typed let', b'bound by name alone'), ('readonly let', b'bound by name alone'),
         ('not own statement', b'taken by a statement of its own'), ('takes value', b'gives a value, not a place'), ('takes failing', b'may give another value'),
         ('lock_all bare', b'lock_all may give'), ('lock_all nameless', b'bound by name, one for each'), ('lock_all pattern', b'bound by name, one for each'), ('lock_all count', b'one name for each lock'),
         ('lock_all not own', b'statement of their own'), ('lock_all temporary', b'locks in variables'), ('lock_all global', b'locks in local variables'),
         ('scan closure', b'cannot keep the place'), ('scan keep', b'cannot be kept'), ('scan pass root', b'passed whole'), ('scan replace', b'cannot be replaced'),
         ('scan second lock', b'take them together'), ('scan second other', b'a second place from it'), ('scan lambda', b'cannot keep the place'),
         ('match value', b'gives a value, not a place'), ('match always', b'always gives its place'), ('match no arm', b'no arm taking the place'), ('match two arms', b'taken by one arm'))


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_place_method_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/place_methods.jo').read_text()
    state = state[state.index('struct PlaceMethod'):]
    outputs = compare_narrow(compiler, tmp_path, release,
                             ('source_types', 'checker_tokens', 'node_store', 'checker_types', 'checker_state', 'place_method_ops'), DRIVER,
                             doubles={'services.jo': SERVICES, 'place_methods.jo': state},
                             invocations=(((), 0), *(((case,), 3) for case, _ in FAILS)),
                             services=('ast', 'check', 'checker_expr', 'deadlock', 'expr', 'lex', 'places', 'refine', 'sibling_types', 'types', 'util'))
    assert outputs[0].endswith(b'all ok\n')
    for output, (_, text) in zip(outputs[1:], FAILS):
        assert text in output, (text, output)
