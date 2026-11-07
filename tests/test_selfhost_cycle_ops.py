"""Import cycles: module order, read summaries, merged initialization and diagnostics match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_tokens.dewy'
use 'source_types.dewy'
const NF_GENERIC = 1
struct Module:
    file: i32
    imports: (int, int)[]
    is_prelude: bool
    init_fn: i32
nodes: Node[] = [Node()]
lists: i32[]
lists2: i32[]
modules: Module[]
files: SrcFile[] = [SrcFile(path="a.jo", is_dewy=false), SrcFile(path="b.dewy", is_dewy=true)]
fns: FnInst[] = [FnInst()]
globals: Global[] = [Global()]
locals: Local[] = [Local()]
dfs_state: bool[]
dp_loaded: int[]
init_fns: int[]
value_equal_fns: {int: int} = {}
value_hash_fns: {int: int} = {}
helper_targets: {int: int[]} = {}
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
kid2 = (n: int, i: int) -> int: int(lists2[int(nodes[n].list2) + i])
nkids2 = (n: int) -> int: int(nodes[n].nlist2)
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
order_modules = (m: int, out: mut int[]):
    if dfs_state[m]: return
    dfs_state[m] = true
    loop edge in modules[m].imports: order_modules(edge.0, out)
    out.push(m)
value_helper_calls = (n: int) -> int[]: helper_targets.get(n) ?? []
isolation_children = (k: NK) -> int:
    if k == .int_lit or k == .ident or k == .bool_lit: return 0
    if k == .str_lit or k == .block or k == .tuple: return 16
    if k == .field or k == .not_ or k == .cast or k == .conv or k == .exprstmt: return 1
    if k == .binary or k == .and_ or k == .or_ or k == .assign: return 3
    if k == .if_: return 7
    if k == .vardecl: return 2
    if k == .call or k == .partial or k == .intrinsic: return 17
    if k == .index: return 19
    if k == .match_: return 32
    -1
fatal = (pos: int, msg: str):
    print("fatal {pos}: {msg}")
    exit(3)
name_of = (n: int) -> str: "n{n}"
pos_file = (pos: int) -> int: pos >> 32
line_col = (pos: int) -> (int, int): (pos & 0xFFFF, 1)
'''

DRIVER = r'''
use 'import_cycles.jo'
fresh = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
module = (dewy: bool, prelude: bool, imports: int[]) -> int:
    edges: (int, int)[]
    loop i in imports: edges.push((i, 0))
    modules.push(Module(file=if dewy: 1 else: 0, imports=edges, is_prelude=prelude))
    modules.len() - 1
global_read = (g: int, pos: int) -> int:
    n = fresh(.ident, pos)
    nodes[n].aux = 2; nodes[n].sym = i32(g)
    n
new_global = (mod: int, name: int, decl: int) -> int:
    globals.push(Global(mod=i32(mod), name=i32(name), decl=i32(decl), fn_accessed=true))
    globals.len() - 1
fn_body = (statements: int[]) -> int:
    b = fresh(.block, 1)
    set_list(b, statements)
    fns.push(FnInst(body=i32(b), decl=i32(fresh(.fn_, 7))))
    nodes[int(fns[fns.len() - 1].decl)].name = i32(fns.len() + 200)
    fns.len() - 1
call_of = (f: int, pos: int) -> int:
    n = fresh(.call, pos)
    nodes[n].sym = i32(f)
    n
decl_with = (value: int, pos: int) -> int:
    n = fresh(.vardecl, pos)
    nodes[n].b = i32(value)
    n
init_of = (m: int, statements: int[]):
    modules[m].init_fn = i32(fn_body(statements))
    init_fns.push(int(modules[m].init_fn))
reset_program = ():
    modules = []
    init_fns = []
    globals = [Global()]
order_case = (label: str, main: int):
    print("{label}: {init_module_order(main)} groups {cycle_groups}")
show_inits = (order: int[]):
    merge_cycle_inits(order)
    loop m in order:
        f = int(modules[m].init_fn)
        print("{m}: init {f} body {kids(int(fns[f].body))} locals {fns[f].locals}")
    print("init_fns {init_fns} merged {cycle_merged.len()}")
reads_of = (s: int) -> int[]:
    out: int[]
    cyc_reads(s, mut out)
    out
main = ():
    case = if args().len() > 1: args()[1] else: "all"
    if case == "all": everything()
    else if case == "single": stuck_single()
    else if case == "pair": stuck_pair()
    else if case == "wait": stuck_wait()
    else if case == "route": stuck_route()
    else if case == "chain": value_chain()
    print("{case} ok")
everything = ():
    # Module order: Jo only; Dewy with no cycle; a Jo cycle; a Dewy cycle, with a prelude and loaded modules.
    a = module(false, false, [])
    modules[a].imports = [(a, 0)]
    b = module(false, false, [a])
    order_case("jo", b)
    reset_program()
    a = module(true, false, [])
    b = module(true, false, [a])
    order_case("plain dewy", b)
    reset_program()
    a = module(false, false, [])
    b = module(false, false, [a])
    modules[a].imports = [(b, 0)]
    c = module(true, false, [b])
    order_case("jo cycle", c)
    print(cycle_edges(c))
    reset_program()
    p = module(true, true, [])
    x = module(true, false, [p])
    y = module(false, false, [x])
    z = module(true, false, [y])
    modules[x].imports.push((z, 0))
    main_m = module(true, false, [z, p])
    order_case("cycle", main_m)
    print("{cycle_edges(x)}")
    dp_loaded = [p]
    print("{cycle_edges(x)} {cycle_edges(p)} {cycle_edges(y)}")
    order_case("with loaded", main_m)
    dp_loaded = []
    # (a cycle only through the prelude, one member left: nothing to merge; and an unreachable loaded module)
    reset_program()
    p = module(true, true, [])
    x = module(true, false, [p])
    modules[p].imports.push((x, 0))
    order_case("prelude cycle", x)
    # Reads: what each statement form reads, first use first, across calls and callable values.
    reset_program()
    m0 = module(true, false, [])
    outside = module(true, false, [])
    g1 = new_global(m0, 1, 0); g2 = new_global(m0, 2, 0); g3 = new_global(m0, 3, 0); g4 = new_global(outside, 4, 0)
    gw = new_global(m0, 5, 0); gi = new_global(m0, 6, 0); ge = new_global(m0, 7, 0); gc = new_global(m0, 8, 0)
    globals[gw].fn_written = true; globals[gi].init_written = true; globals[ge].exposed = true; globals[gc].is_const = true
    plain_decl = fresh(.vardecl, 3)
    globals[g1].decl = i32(plain_decl)
    cyc_reads_start([m0])
    print("{cr_decls.has(plain_decl)} {cr_member} {cr_helpers}")
    value_equal_fns[1] = 1
    cyc_reads_start([m0])
    print(cr_helpers)
    value_equal_fns.clear()
    value_hash_fns[1] = 1
    cyc_reads_start([m0])
    print(cr_helpers)
    value_hash_fns.clear()
    cyc_reads_start([m0])
    show = (label: str, s: int): print("{label}: {reads_of(s)}")
    show("read", global_read(g1, 10))
    show("outside", global_read(g4, 10))
    show("zero", 0)
    show("literal", fresh(.int_lit, 1))
    show("float", fresh(.float_lit, 1))
    pair = fresh(.binary, 2); nodes[pair].a = i32(global_read(g1, 11)); nodes[pair].b = i32(global_read(g2, 12))
    show("binary, first use wins", pair)
    twice = fresh(.block, 2); set_list(twice, [global_read(g1, 13), global_read(g1, 14), global_read(g2, 15)])
    show("block", twice)
    stmt = fresh(.exprstmt, 2); nodes[stmt].a = i32(global_read(g3, 16))
    show("tail a", stmt)
    declared = decl_with(global_read(g3, 17), 2)
    show("tail b", declared)
    branch = fresh(.if_, 2); nodes[branch].a = i32(global_read(g1, 18)); nodes[branch].b = i32(global_read(g2, 19)); nodes[branch].c = i32(global_read(g3, 20))
    show("if", branch)
    idx = fresh(.index, 2); nodes[idx].a = i32(global_read(g1, 21)); nodes[idx].b = i32(global_read(g2, 22)); set_list(idx, [global_read(g3, 23)])
    show("index", idx)
    unknown = fresh(.lambda, 2); nodes[unknown].a = i32(global_read(g1, 24)); nodes[unknown].b = i32(global_read(g2, 25)); set_list(unknown, [global_read(g3, 26)])
    show("unknown kind", unknown)
    second_list = fresh(.match_, 2)
    nodes[second_list].list2 = i32(lists2.len()); nodes[second_list].nlist2 = 1
    lists2.push(i32(global_read(g2, 27)))
    show("second list", second_list)
    assign = fresh(.assign, 2); nodes[assign].op = i32(int(Tok.assign)); nodes[assign].a = i32(global_read(g1, 28)); nodes[assign].b = i32(global_read(g2, 29))
    show("assign needs target", assign)
    compound = fresh(.assign, 2); nodes[compound].op = i32(int(Tok.pluseq)); nodes[compound].a = i32(global_read(g1, 30)); nodes[compound].b = i32(global_read(g2, 31))
    show("compound reads target", compound)
    target_field = fresh(.field, 2); nodes[target_field].a = i32(global_read(g1, 32))
    fa = fresh(.assign, 2); nodes[fa].op = i32(int(Tok.assign)); nodes[fa].a = i32(target_field); nodes[fa].b = i32(global_read(g2, 33))
    show("field target reads", fa)
    many = fresh(.tuple, 2); set_list(many, [global_read(g1, 34), target_field, 0])
    ta = fresh(.assign, 2); nodes[ta].op = i32(int(Tok.assign)); nodes[ta].a = i32(many); nodes[ta].b = i32(global_read(g2, 35))
    show("tuple target", ta)
    # Calls: direct, through callables, recursion shares a component's summary; lazily sized tables.
    leaf = fn_body([global_read(g1, 40)])
    mid = fn_body([call_of(leaf, 41), global_read(g2, 42)])
    self_a = fn_body([global_read(g3, 43)])
    self_b = fn_body([call_of(self_a, 44), global_read(g2, 45)])
    set_list(int(fns[self_a].body), [global_read(g3, 43), call_of(self_b, 46)])
    show("call", call_of(mid, 50))
    show("call again", call_of(mid, 51))
    show("recursion", call_of(self_a, 52))
    show("recursion other", call_of(self_b, 53))
    show("out of range", call_of(9999, 54))
    show("no function", call_of(0, 55))
    print("{cr_comp[leaf]} {cr_comp[mid]} {cr_comp[self_a] == cr_comp[self_b]} {cr_sets}")
    callee = (via: int, aux: int) -> int:
        n = fresh(.call, 60)
        nodes[n].a = i32(via); nodes[n].aux = i32(aux)
        n
    fnref = fresh(.fnref, 2); nodes[fnref].sym = i32(leaf)
    lam = fresh(.lambda, 2); nodes[lam].sym = i32(mid)
    generic = fresh(.lambda, 2); nodes[generic].sym = i32(mid); nodes[generic].flags = 1
    partial0 = fresh(.partial, 2); nodes[partial0].sym = i32(leaf)
    partial1 = fresh(.partial, 2); nodes[partial1].aux = 1; nodes[partial1].a = i32(fnref)
    conv = fresh(.conv, 2); nodes[conv].a = i32(fnref)
    cast = fresh(.cast, 2); nodes[cast].a = i32(lam)
    held = new_global(m0, 9, decl_with(fnref, 3))
    held_kids = new_global(m0, 10, decl_with(fnref, 3))
    set_list(int(globals[held_kids].decl), [fresh(.int_lit, 1)])
    held_none = new_global(m0, 11, 0)
    held_self = new_global(m0, 12, 0)
    self_ref = global_read(held_self, 3)
    globals[held_self].decl = i32(decl_with(self_ref, 3))
    loop via in [fnref, lam, generic, partial0, partial1, conv, cast, 0, -1, fresh(.int_lit, 2), global_read(held, 3), global_read(held, 3), global_read(held_kids, 3), global_read(held_none, 3), global_read(held_self, 3), global_read(gw, 3), global_read(gi, 3), global_read(ge, 3), global_read(gc, 3)]:
        print("callable {cyc_callable(via)}")
    show("via 1", callee(fnref, 1))
    show("via 4", callee(lam, 4))
    show("via 2", callee(fnref, 2))
    # Equality and hash helpers run at operators and intrinsics only with user helpers.
    op = fresh(.binary, 2)
    helper_targets[op] = [leaf, mid]
    show("no helper", op)
    cr_helpers = true
    show("helper", op)
    intrinsic = fresh(.intrinsic, 2)
    helper_targets[intrinsic] = [self_a]
    show("intrinsic helper", intrinsic)
    cr_helpers = false
    # Where.
    print("{cyc_where(5)} {cyc_where((1 << 32) | 9)} {cyc_where(-1)} {cyc_where(9 << 32)}")
    # Blockers.
    print("{cyc_blocker([], [0, 0], 2)} {cyc_blocker([2, 1, 1, 0], [0, 0], 2)} {cyc_blocker([2, 1, 1, 0], [2, 0], 2)} {cyc_blocker([2, 1, 1, 0, 3, 1, 1, 0], [2, 0], 2)} {cyc_blocker([2, 1, 1, 0, 3, 1, 1, 0], [2, 2], 2)}")
    # Merging: single files stay put; a two-member cycle interleaves; locals and init functions move.
    reset_program()
    cycle_groups = []
    cycle_merged = {}
    m0 = module(true, false, [])
    m1 = module(true, false, [])
    solo = module(true, false, [])
    pre = module(true, true, [])
    d0 = fresh(.vardecl, 100)
    d1 = decl_with(0, 110)
    g_a = new_global(m0, 21, d0)
    g_b = new_global(m1, 22, d1)
    nodes[d1].b = i32(global_read(g_a, 111))
    using = fn_body([global_read(g_b, 120)])
    s0 = decl_with(call_of(using, 101), 102)
    d_after = fresh(.vardecl, 130)
    g_c = new_global(m0, 23, d_after)
    init_of(m0, [d0, s0, d_after])
    init_of(m1, [d1])
    solo_decl = fresh(.vardecl, 140)
    g_solo = new_global(solo, 24, solo_decl)
    globals[g_solo].fn_accessed = false
    init_of(solo, [solo_decl, fresh(.exprstmt, 141)])
    init_of(pre, [fresh(.exprstmt, 150)])
    locals.push(Local())
    fns[int(modules[m1].init_fn)].locals = [1]
    cycle_groups = [[m1, m0]]
    print(g_c)
    show_inits([pre, m0, m1, solo])
    print(locals[1].owner)
    # No cycles: single-file checks, reads in order, nothing changes.
    reset_program()
    cycle_groups = []
    cycle_merged = {}
    ok = module(true, false, [])
    first = fresh(.vardecl, 200)
    new_global(ok, 25, first)
    second = decl_with(0, 201)
    g_second = new_global(ok, 26, second)
    nodes[second].b = i32(global_read(globals.len() - 2, 202))
    init_of(ok, [first, second, fresh(.exprstmt, 203)])
    no_shared = module(true, false, [])
    init_of(no_shared, [fresh(.exprstmt, 204)])
    show_inits([ok, no_shared])
    # A value cycle within one module stands; an unrelated global returns.
    ensuring_globals = []
    global_cycle_across_modules(g_second, 1)
    ensuring_globals = [g_second]
    global_cycle_across_modules(g_second, 2)
    global_cycle_across_modules(1, 3)
# A statement reads a later declaration of its own file.
stuck_single = ():
    reset_program()
    m = module(true, false, [])
    d = fresh(.vardecl, 300)
    g = new_global(m, 31, d)
    reader = decl_with(global_read(g, 301), 302)
    init_of(m, [reader, d])
    merge_cycle_inits([m])
# Two members each need the other's value.
stuck_pair = ():
    reset_program()
    a = module(true, false, [])
    b = module(true, false, [])
    da = decl_with(0, 310); db = decl_with(0, 320)
    ga = new_global(a, 32, da); gb = new_global(b, 33, db)
    nodes[da].b = i32(global_read(gb, 311))
    nodes[db].b = i32(global_read(ga, 321))
    init_of(a, [da])
    init_of(b, [db])
    cycle_groups = [[a, b]]
    merge_cycle_inits([a, b])
# The order waits behind an earlier statement.
stuck_wait = ():
    reset_program()
    a = module(true, false, [])
    b = module(true, false, [])
    da1 = decl_with(0, 330); da2 = decl_with(0, 331); db = decl_with(0, 340)
    ga1 = new_global(a, 34, da1); ga2 = new_global(a, 35, da2); gb = new_global(b, 36, db)
    nodes[da1].b = i32(global_read(gb, 332))
    nodes[da2].b = i32(fresh(.int_lit, 333))
    nodes[db].b = i32(global_read(ga2, 341))
    init_of(a, [da1, da2])
    init_of(b, [db])
    cycle_groups = [[a, b]]
    print(ga1)
    merge_cycle_inits([a, b])
# A read through calls names its route, past a function that reads nothing.
stuck_route = ():
    reset_program()
    a = module(true, false, [])
    b = module(true, false, [])
    da = decl_with(0, 350); db = decl_with(0, 360)
    ga = new_global(a, 37, da); gb = new_global(b, 38, db)
    empty = fn_body([])
    reader = fn_body([global_read(gb, 370)])
    mid = fn_body([call_of(empty, 371), call_of(reader, 372), call_of(reader, 373)])
    back = fn_body([global_read(ga, 374)])
    nodes[da].b = i32(call_of(mid, 351))
    nodes[db].b = i32(call_of(back, 361))
    init_of(a, [da])
    init_of(b, [db])
    cycle_groups = [[a, b]]
    merge_cycle_inits([a, b])
value_chain = ():
    reset_program()
    a = module(true, false, [])
    b = module(true, false, [])
    c = module(true, false, [])
    ga = new_global(a, 41, fresh(.vardecl, 400))
    gb = new_global(b, 42, fresh(.vardecl, 401))
    gc = new_global(c, 43, fresh(.vardecl, 402))
    ensuring_globals = [ga, gb, gc]
    global_cycle_across_modules(ga, 403)
'''

CASES = (((), 0), (('single',), 3), (('pair',), 3), (('wait',), 3), (('route',), 3), (('chain',), 3))


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_cycle_ops_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/import_cycles.jo').read_text()
    state = state[state.index('cycle_groups: int[][]'):]
    outputs = compare_narrow(compiler, tmp_path, release,
                             ('checker_tokens', 'source_types', 'node_store', 'checker_types', 'checker_state', 'cycle_ops'), DRIVER,
                             doubles={'services.jo': SERVICES, 'import_cycles.jo': state},
                             invocations=CASES,
                             services=('ast', 'check', 'isolation', 'isolation_ops', 'lower', 'lower_helpers', 'prelude', 'util'))
    assert outputs[0].endswith(b'all ok\n')
    for output, text in zip(outputs[1:], (b'is used before it has its value', b'a value cycle across modules', b'has no order that gives it first', b' -> accesses ', b'which needs ')):
        assert text in output, (text, output)
