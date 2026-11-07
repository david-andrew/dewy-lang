"""Growing exact values: expression readings, carried bindings and warnings match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
const NF_BROADCAST = 1
const NF_RDONLY = 2
const T_INT = 1
const T_MATH_INT = 2
const T_BIG = 3
const T_RATIONAL = 4
const T_FLOAT = 5
const T_TEXT = 6
struct Watch:
    growth: int
nodes: Node[] = [Node()]
lists: i32[]
syms: Sym[] = [Sym()]
locals: Local[] = [Local()]
globals: Global[] = [Global()]
ctxs: FnCtx[] = [FnCtx(inst=5, loop_depth=1)]
cx = 0
loop_serials: int[] = [1, 2]
statement_watch = Watch(0)
scope: {int: int} = {}
decimal_floats: {int: bool} = {}
decimal_frame = 0
decimal_locals: {int: int} = {}
decimal_globals: {int: int} = {}
decimal_cached_type = 0
ide_on = false
names: {str: int} = {"__dewy_divide": 1000, "__dewy_power": 1001}
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
lookup = (name: int) -> int: scope.get(name) ?? 0
dewy_at = (pos: int) -> bool: pos < 1000000
pos_in_lib = (pos: int) -> bool: pos >= 500000
intern = (s: str) -> int: names[s]
warn = (p: int, msg: str): print("warn {p}: {msg}")
prune = (t: int) -> int: t
tkind = (t: int) -> TK: if t == T_RATIONAL: .struct_ else if t == T_TEXT: .str_ else: .int_
is_int = (t: int) -> bool: t == T_INT
is_float = (t: int) -> bool: t == T_FLOAT
bundled_bigint_type = (t: int) -> bool: t == T_BIG
bundled_rational_type = (t: int) -> bool: t == T_RATIONAL
'''

DRIVER = r'''
use 'growth.jo'
fresh = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
ident = (name: int) -> int:
    n = fresh(.ident, 7)
    nodes[n].name = i32(name)
    n
ilit = (v: int) -> int:
    n = fresh(.int_lit, 7)
    nodes[n].ival = v
    n
flit = (v: float64, text: bool) -> int:
    n = fresh(.float_lit, 7)
    nodes[n].fval = v
    if text: nodes[n].sval = 1
    n
bin = (op: Tok, a: int, b: int) -> int:
    n = fresh(.binary, 7)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
un = (op: Tok, a: int) -> int:
    n = fresh(.unary, 7)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(a)
    n
call = (name: int, x: int, y: int) -> int:
    n = fresh(.call, 7)
    nodes[n].a = i32(ident(name))
    node_set_list(mut nodes, mut lists, n, [x, y])
    n
gtext = (g: Growth) -> str: "{g.num}/{g.den} grows={g.grows} cls={g.cls} unit={g.unit} whole={g.whole}"
reading = (n: int, key: int): print(gtext(growth_expr(n, key)))
bind_local = (name: int, t: int, owner: int, dloops: int) -> int:
    locals.push(Local(type=i32(t), owner=i32(owner), dloops=i32(dloops)))
    syms.push(Sym(kind=.local, ref=i32(locals.len() - 1)))
    scope[name] = syms.len() - 1
    locals.len() - 1
assign = (op: Tok, target: int, right: int, sval: int, pos: int) -> int:
    n = fresh(.assign, pos)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(target); nodes[n].b = i32(right); nodes[n].sval = i32(sval)
    if target != 0: nodes[target].pos = pos
    n
main = ():
    print("{gtext(growth_free(GROWTH_INT))} {gtext(growth_free(GROWTH_OTHER))}")
    print("{growth_dep(Growth(1, 0, false, 0))} {growth_dep(Growth(0, 1, false, 0))} {growth_dep(Growth(0, 0, true, 0))} {growth_dep(Growth(0, 0, false, 0))}")
    # The carried binding a name is.
    x = bind_local(10, T_RATIONAL, 5, 0)
    growth_inferred[x] = false
    whole = bind_local(11, T_RATIONAL, 5, 0)
    growth_inferred[whole] = true
    not_inferred = bind_local(12, T_RATIONAL, 5, 0)
    other_owner = bind_local(13, T_RATIONAL, 9, 0)
    growth_inferred[other_owner] = false
    inner = bind_local(14, T_RATIONAL, 5, 2)
    growth_inferred[inner] = false
    n_int = bind_local(15, T_INT, 5, 0)
    n_float = bind_local(16, T_FLOAT, 5, 0)
    n_rat = bind_local(17, T_RATIONAL, 5, 0)
    n_text = bind_local(18, T_TEXT, 5, 0)
    decl = fresh(.vardecl, 1)
    global_bind = (name: int, t: int, d: int) -> int:
        globals.push(Global(type=i32(t), decl=i32(d)))
        syms.push(Sym(kind=.global, ref=i32(globals.len() - 1)))
        scope[name] = syms.len() - 1
        globals.len() - 1
    g_ok = global_bind(20, T_RATIONAL, decl)
    global_bind(21, T_RATIONAL, 0)
    global_bind(22, 0, decl)
    annotated = fresh(.vardecl, 1); nodes[annotated].a = 1
    global_bind(23, T_RATIONAL, annotated)
    readonly = fresh(.vardecl, 1); nodes[readonly].flags = 2
    global_bind(24, T_RATIONAL, readonly)
    global_bind(25, T_RATIONAL, fresh(.block, 1))
    global_bind(26, T_INT, decl)
    syms.push(Sym(kind=.fns)); scope[30] = syms.len() - 1
    loop name in [10, 11, 12, 13, 14, 15, 20, 21, 22, 23, 24, 25, 26, 30, 99]:
        print("key {name} {growth_key(lookup(name))}")
    print(growth_key(0))
    loop t in [0, T_INT, T_MATH_INT, T_BIG, T_RATIONAL, T_FLOAT, T_TEXT]: print(growth_type_class(t))
    classes = [GROWTH_INT, GROWTH_FRAC, GROWTH_OTHER, GROWTH_FLOAT]
    loop a in classes:
        row = ""
        loop b in classes: row = "{row} {growth_join(a, b)}"
        print(row)
    # Readings of every syntactic form, against the binding x.
    key = x
    reading(0, key)
    loop v in [1, -1, 0, 2]: reading(ilit(v), key)
    loop v in [1.0, -1.0, 2.0, 0.5, 1e300, -1e300, 9007199254740992.0, -9007199254740992.0]: reading(flit(v, true), key)
    reading(flit(1.5, false), key)
    reading(ident(10), key)
    reading(ident(99), key)
    reading(ident(11), key)
    loop name in [15, 16, 17, 18, 20, 26, 30]: reading(ident(name), key)
    reading(un(.minus, ident(10)), key)
    reading(un(.plus, ident(10)), key)
    reading(un(.tilde, ident(10)), key)
    broad = un(.minus, ident(10)); nodes[broad].flags = 1
    reading(broad, key)
    loop op in [Tok.plus, Tok.minus, Tok.star, Tok.percent]: reading(bin(op, ident(10), ilit(2)), key)
    broad_bin = bin(.plus, ident(10), ident(10)); nodes[broad_bin].flags = 1
    reading(broad_bin, key)
    reading(call(1000, ident(10), ilit(2)), key)
    reading(call(1001, ident(10), ilit(2)), key)
    reading(call(77, ident(10), ilit(2)), key)
    one_arg = call(1000, ident(10), ilit(2)); nodes[one_arg].nlist = 1
    reading(one_arg, key)
    broad_call = call(1000, ident(10), ilit(2)); nodes[broad_call].flags = 1
    reading(broad_call, key)
    no_callee = call(1000, ident(10), ilit(2)); nodes[no_callee].a = 0
    reading(no_callee, key)
    field_callee = call(1000, ident(10), ilit(2)); nodes[field_callee].a = i32(fresh(.field, 1))
    reading(field_callee, key)
    reading(fresh(.call, 1), key)
    # Temporaries.
    t1 = bind_local(40, T_RATIONAL, 5, 2)
    growth_temps[t1] = [GrowthTemp(x, Growth(2, 0, false, GROWTH_INT)), GrowthTemp(whole, Growth(1, 1, true, GROWTH_FRAC))]
    reading(ident(40), x)
    reading(ident(40), whole)
    reading(ident(40), n_int)
    # The algebra, over a small table of readings.
    samples = [Growth(0, 0, false, GROWTH_INT, true, true), Growth(0, 0, false, GROWTH_INT, false, true), Growth(0, 0, false, GROWTH_FRAC), Growth(0, 0, false, GROWTH_FLOAT), Growth(0, 0, true, GROWTH_OTHER), Growth(1, 0, false, GROWTH_INT, false, true), Growth(1, 1, false, GROWTH_FRAC), Growth(0, 1, false, GROWTH_INT), Growth(2, 3, true, GROWTH_FLOAT)]
    loop a in samples:
        loop b in samples:
            print("{gtext(growth_add(a, b))} | {gtext(growth_mul(a, b))} | {gtext(growth_div(a, b))}")
        print(growth_grows(a))
    loop a in samples:
        loop e in [ilit(0), ilit(2), ilit(-1), ilit(-3), ilit(64), ilit(65), ilit(-64), ilit(-65), ident(10)]:
            print(gtext(growth_power(a, e)))
    # Whether anything needs looking at.
    print(growth_on())
    saved_inferred = growth_inferred
    growth_inferred = {}
    print(growth_on())
    decimal_cached_type = 1
    print(growth_on())
    decimal_cached_type = 0
    growth_inferred = saved_inferred
    ctxs[0].loop_depth = 0
    print(growth_on())
    ctxs[0].loop_depth = 1
    cx = -1
    print(growth_on())
    growth_assign(1)
    cx = 0
    # Assignments: refused forms, then each operator.
    target = () -> int: ident(10)
    growth_assign(assign(.assign, 0, ilit(1), 0, 1))
    growth_assign(assign(.assign, fresh(.field, 1), ilit(1), 0, 2))
    nb = assign(.assign, target(), bin(.star, ident(10), ident(10)), 0, 3); nodes[nb].flags = 1
    growth_assign(nb)
    growth_assign(assign(.assign, target(), bin(.star, ident(10), ident(10)), 0, 1000001))
    growth_assign(assign(.assign, target(), bin(.star, ident(10), ident(10)), 0, 500001))
    growth_assign(assign(.assign, ident(12), bin(.star, ident(12), ident(12)), 0, 4))
    p = 100
    next_at = () -> int:
        p += 1
        p
    growth_assign(assign(.assign, target(), bin(.star, ident(10), ident(10)), 0, next_at()))
    growth_assign(assign(.assign, target(), bin(.plus, ident(10), ilit(1)), 0, next_at()))
    growth_assign(assign(.slasheq, target(), ilit(2), 1000, next_at()))
    growth_assign(assign(.slasheq, target(), ilit(1), 1000, next_at()))
    growth_assign(assign(.slasheq, target(), ilit(2), 1001, next_at()))
    growth_assign(assign(.slasheq, target(), ilit(2), 55, next_at()))
    growth_assign(assign(.stareq, target(), flit(1.5, true), 0, next_at()))
    growth_assign(assign(.stareq, target(), ilit(3), 0, next_at()))
    growth_assign(assign(.pluseq, target(), bin(.star, ident(10), ident(10)), 0, next_at()))
    growth_assign(assign(.minuseq, target(), ilit(1), 0, next_at()))
    growth_assign(assign(.percenteq, target(), ilit(1), 0, next_at()))
    # (a whole start keeps polynomials whole; a global's key)
    growth_assign(assign(.assign, ident(11), bin(.star, ident(11), ident(11)), 0, next_at()))
    growth_assign(assign(.assign, ident(11), call(1000, ident(11), ident(11)), 0, next_at()))
    growth_assign(assign(.assign, ident(20), bin(.star, ident(20), ident(20)), 0, next_at()))
    # Deferred by a decimal that may still turn float.
    decimal_locals[x] = 200
    decimal_globals[g_ok] = 201
    decimal_frame = 1
    growth_assign(assign(.assign, target(), bin(.star, ident(10), ident(10)), 0, 150))
    growth_assign(assign(.assign, target(), bin(.star, ident(10), ident(10)), 0, 150))
    growth_assign(assign(.assign, target(), bin(.star, ident(10), ident(10)), 0, 151))
    growth_assign(assign(.assign, ident(20), bin(.star, ident(20), ident(20)), 0, 152))
    print(growth_pending.len())
    decimal_frame = 0
    growth_assign(assign(.assign, target(), bin(.star, ident(10), ident(10)), 0, 153))
    decimal_frame = 1
    decimal_floats[201] = true
    growth_flush()
    growth_flush()
    decimal_floats.clear(); decimal_locals.clear(); decimal_globals.clear(); decimal_frame = 0
    # The same place warns once, except in an editor.
    growth_warn(160)
    growth_warn(160)
    ide_on = true
    growth_warn(160)
    ide_on = false
    # Declarations: starts, temporaries, publication.
    vd = (a: int, b: int, pos: int) -> int:
        n = fresh(.vardecl, pos)
        nodes[n].a = i32(a); nodes[n].b = i32(b)
        n
    status = (): print("{growth_start_whole} {growth_pending_n} {growth_pending_temps.len()} {statement_watch.growth} {growth_inferred.len()} {growth_temps.len()}")
    loop d in [vd(0, 0, 1), vd(1, ilit(1), 1), vd(0, ilit(1), 1), vd(0, flit(2.0, true), 1), vd(0, flit(2.5, true), 1), vd(0, flit(2.0, false), 1), vd(0, ident(10), 1000001)]:
        growth_decl_before(d)
        status()
    d1 = vd(0, bin(.star, ident(10), ident(11)), 1)
    growth_decl_before(d1)
    status()
    l1 = bind_local(41, T_INT, 5, 2)
    growth_decl_after(d1, l1, T_INT)
    status()
    growth_decl_before(vd(0, ilit(2), 1))
    growth_decl_after(vd(0, ilit(2), 1), bind_local(42, T_RATIONAL, 5, 0), T_RATIONAL)
    status()
    print(growth_inferred[locals.len() - 1])
    growth_decl_before(vd(0, ident(99), 1))
    growth_decl_after(vd(0, ident(99), 1), bind_local(43, T_TEXT, 5, 0), T_TEXT)
    growth_decl_after(vd(1, ident(99), 1), bind_local(44, T_RATIONAL, 5, 0), T_RATIONAL)
    growth_decl_after(vd(0, ident(99), 1000001), bind_local(45, T_RATIONAL, 5, 0), T_RATIONAL)
    ro = vd(0, ident(99), 1); nodes[ro].flags = 2
    growth_decl_after(ro, bind_local(46, T_RATIONAL, 5, 0), T_RATIONAL)
    status()
    # Which bindings an expression reads, capped.
    keys_of = (n: int):
        keys: int[]
        growth_keys_in(n, mut keys)
        print(keys)
    keys_of(0)
    keys_of(ident(10))
    keys_of(ident(99))
    keys_of(ident(15))
    keys_of(ident(40))
    keys_of(un(.minus, ident(10)))
    keys_of(bin(.plus, ident(10), ident(10)))
    keys_of(bin(.plus, ident(10), ident(11)))
    keys_of(bin(.plus, ident(40), ident(20)))
    keys_of(call(1000, ident(10), ident(20)))
    many: int[]
    k0 = bind_local(50, T_RATIONAL, 5, 0); growth_inferred[k0] = false
    k1 = bind_local(51, T_RATIONAL, 5, 0); growth_inferred[k1] = false
    k2 = bind_local(52, T_RATIONAL, 5, 0); growth_inferred[k2] = false
    k3 = bind_local(53, T_RATIONAL, 5, 0); growth_inferred[k3] = false
    wide = bin(.plus, bin(.plus, ident(50), ident(51)), bin(.plus, bin(.plus, ident(52), ident(53)), ident(10)))
    growth_keys_in(wide, mut many)
    print(many)
    cap: int[] = [k0, k1, k2]
    growth_keys_in(ident(40), mut cap)
    print(cap)
    print("growth ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_growth_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/growth.jo').read_text()
    state = state[state.index('const GROWTH_INT'):]
    output = compare_narrow(compiler, tmp_path, release,
                            ('checker_tokens', 'node_store', 'checker_types', 'checker_state', 'growth_ops'), DRIVER,
                            doubles={'services.jo': SERVICES, 'growth.jo': state},
                            services=('ast', 'check', 'checker_expr', 'decimals', 'decimal_ops', 'expr', 'ide', 'lex', 'types', 'units', 'util'))
    assert output.endswith(b'growth ok\n')
    assert output.count(b'this exact value grows') >= 8
