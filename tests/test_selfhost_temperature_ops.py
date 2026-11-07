"""Literal-only temperature bindings: use classification, partners, warnings and rewrites match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
const NF_AT = 1
const NF_CHECKED = 2
const NF_GLOBAL = 4
const NF_MUT = 8
const LF_CAPTURE = 1
const T_PLAIN = 1
const T_POINT = 2
const T_DELTA = 3
const T_KELVIN = 4
const T_LENGTH = 5
const T_POINTS = 6
const T_INT = 7
const T_NO_ORIGIN = 8
const T_MADE = 20
struct QuantityInfo:
    origin: int
    display: int
struct Module:
    decls: int[]
    inits: int[]
struct Watch:
    temperature_writes: int
nodes: Node[] = [Node()]
lists: i32[]
lists2: i32[]
syms: Sym[] = [Sym()]
locals: Local[] = [Local()]
globals: Global[] = [Global()]
modules: Module[] = [Module()]
types: TypeInfo[] = [TypeInfo(), TypeInfo(), TypeInfo(), TypeInfo(), TypeInfo(), TypeInfo(), TypeInfo(kind=.array, elem=2), TypeInfo()]
quantity_tags: QuantityInfo[] = [QuantityInfo(0, 0), QuantityInfo(70, 71), QuantityInfo(70, 0), QuantityInfo(0, 0)]
statement_watch = Watch(0)
scope: {int: int} = {}
last_checked = 0
sibling_block = 0
sibling_index = 0
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
kid_c = (n: int) -> int: int(nodes[n].c)
kid_d = (n: int) -> int: int(nodes[n].d)
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
kids2 = (n: int) -> int[]:
    out: int[]
    loop i in [0..int(nodes[n].nlist2)): out.push(int(lists2[int(nodes[n].list2) + i]))
    out
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
ensure_global = (g: int, pos: int, in_flow: bool = false):
    print("ensure_global {g} {pos} {in_flow}")
    globals[g].state = 2
lookup = (name: int) -> int: scope.get(name) ?? 0
cx_token = (x: int) -> Tok: x as Tok
ntype = (n: int) -> int: int(nodes[n].type)
coerce = (e: int, t: int) -> int:
    print("coerce {e} {t}")
    n = nodes.len()
    copy = nodes[e]
    nodes.push(copy)
    nodes[n].type = i32(t)
    n
source_force_body = (d: int): print("force {d}")
prune = (t: int) -> int: t
tkind = (t: int) -> TK: types[t].kind
type_eq = (a: int, b: int) -> bool: a == b
base_dimension = (i: int) -> int: 400 + i
is_quantity = (t: int) -> bool: t == T_POINT or t == T_DELTA or t == T_KELVIN or t == T_LENGTH or t == T_NO_ORIGIN or t >= T_MADE
quantity_dimension = (t: int) -> int: if t == T_LENGTH: 401 else: 404
quantity_is_delta = (t: int) -> bool: t == T_DELTA
quantity_point = (t: int) -> bool: t == T_POINT or t == T_NO_ORIGIN
quantity_tag = (t: int) -> int: if t == T_POINT: 1 else if t == T_NO_ORIGIN: 3 else: 2
quantity_base = (t: int) -> int: if t == T_NO_ORIGIN: 501 else: 500
quantity_delta_reading = (n: int) -> int:
    print("delta_reading {n}")
    n
quantity_retag = (e: int, tag: int): print("retag {e} {tag}")
intern_quantity_tag = (unit: int, origin: int, delta: bool) -> int:
    print("intern_tag {unit} {origin} {delta}")
    9
mk_quantity = (base: int, dim: int) -> int:
    print("mk_quantity {base} {dim}")
    T_MADE
line_col = (pos: int) -> (int, int): (pos, 1)
name_of = (n: int) -> str: "n{n}"
pos_in_lib = (pos: int) -> bool: pos >= 100000
warn = (pos: int, msg: str): print("warn {pos}: {msg}")
'''

DRIVER = r'''
use 'temperature_kinds.jo'
const CELSIUS = 70
const KELVIN = 71
const LENGTH = 72
fresh = (k: NK) -> int:
    nodes.push(Node(kind=k, pos=nodes.len()))
    nodes.len() - 1
ident = (name: int) -> int:
    n = fresh(.ident)
    nodes[n].name = i32(name)
    n
ilit = (v: int) -> int:
    n = fresh(.int_lit)
    nodes[n].ival = v
    n
flit = (v: float64) -> int:
    n = fresh(.float_lit)
    nodes[n].fval = v
    n
bin = (op: Tok, a: int, b: int) -> int:
    n = fresh(.binary)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
dot = (c: int, a: int, b: int) -> int:
    n = bin(.dotop, a, b)
    nodes[n].aux = i32(c)
    n
neg = (a: int) -> int:
    n = fresh(.unary)
    nodes[n].op = i32(int(Tok.minus)); nodes[n].a = i32(a)
    n
temp = (v: int, unit: int) -> int: bin(.star, ilit(v), ident(unit))
assign = (op: Tok, a: int, b: int) -> int:
    n = fresh(.assign)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
vardecl = (name: int, value: int) -> int:
    n = fresh(.vardecl)
    nodes[n].name = i32(name); nodes[n].b = i32(value)
    n
block = (items: int[]) -> int:
    n = fresh(.block)
    node_set_list(mut nodes, mut lists, n, items)
    n
checked = (n: int, t: int) -> int:
    nodes[n].flags = i32(int(nodes[n].flags) | NF_CHECKED)
    nodes[n].type = i32(t)
    n
bind_local = (name: int, t: int) -> int:
    locals.push(Local(type=i32(t)))
    syms.push(Sym(kind=.local, ref=i32(locals.len() - 1)))
    scope[name] = syms.len() - 1
    locals.len() - 1
bind_global = (name: int, t: int, state: int, decl: int) -> int:
    globals.push(Global(type=i32(t), state=i32(state), decl=i32(decl)))
    syms.push(Sym(kind=.global, ref=i32(globals.len() - 1)))
    scope[name] = syms.len() - 1
    globals.len() - 1
show = () -> str: "name={tks.name} unit={tks.unit} self={tks.self_decl} open={tks.open} mediate={tks.mediate} p={tks.p_use} d={tks.d_use} neutral={tks.neutral_sub} pd={tks.p_direct} dd={tks.d_direct} reads={tks.d_reads} writes={tks.writes}"
reset_scan = ():
    tks = TkScan(name=50, unit=CELSIUS, self_decl=0)
    tk_decls = []
    tk_direct = {}
    tk_bindings = {}
    tk_deciding = {}
use_at = (n: int):
    reset_scan()
    tk_use(n)
    print(show())
walk_at = (n: int):
    reset_scan()
    tk_walk(n)
    print("{show()} decls {tk_decls.len()}")
me = () -> int: ident(50)
main = ():
    loop types.len() < 25: types.push(TypeInfo())
    g_c = bind_global(CELSIUS, T_POINT, 2, fresh(.vardecl))
    g_k = bind_global(KELVIN, T_KELVIN, 2, fresh(.vardecl))
    g_l = bind_global(LENGTH, T_LENGTH, 2, fresh(.vardecl))
    print("{g_c} {g_k} {g_l}")
    # Literals and units.
    loop e in [0, checked(temp(1, CELSIUS), T_POINT), temp(20, CELSIUS), neg(temp(5, CELSIUS)), bin(.star, flit(1.5), ident(CELSIUS)), bin(.star, ident(1), ident(CELSIUS)), bin(.star, ilit(2), ilit(3)), bin(.plus, ilit(2), ident(CELSIUS)), ident(1), neg(ident(1))]:
        print(tk_literal_unit(e))
    bound = bind_global(73, T_NO_ORIGIN, 2, fresh(.vardecl))
    print(bound)
    loop nm in [CELSIUS, KELVIN, LENGTH, 73, 74, CELSIUS, 74]: print("offset {nm} {tk_offset_unit(nm)}")
    local_name = bind_local(75, T_POINT)
    print("{local_name} {tk_offset_unit(75)}")
    lazy_decl = fresh(.vardecl)
    lazy = bind_global(76, T_POINT, 0, lazy_decl)
    print("{tk_settled(lazy)} {globals[lazy].state}")
    nodes[lazy_decl].pos = 200000
    globals[lazy].state = 0
    print("{tk_settled(lazy)} {globals[lazy].state}")
    loop e in [ident(CELSIUS), ident(KELVIN), ident(LENGTH), ident(99), checked(ident(CELSIUS), T_POINT), ident(75), fresh(.call)]: print("unit name {tk_unit_name(e)}")
    tk_decls = [TkDecl(CELSIUS, 0, 0, 0), TkDecl(1, 0, 0, 0)]
    print("{tk_find(CELSIUS)} {tk_find(1)} {tk_find(2)} {tk_unit_name(ident(CELSIUS))}")
    tks = TkScan(name=50)
    print("{tk_self(0)} {tk_self(ident(50))} {tk_self(ident(51))} {tk_self(checked(ident(50), 1))} {tk_self(fresh(.call))}")
    tk_decls.push(TkDecl(50, 0, 0, 0))
    print(tk_self(ident(50)))
    tk_decls = []
    loop t in [T_POINT, T_DELTA, T_KELVIN, T_LENGTH, T_INT, T_POINTS, T_NO_ORIGIN]: print("class {t} {tk_type_class(t)}")
    print("{tk_decl_value(vardecl(1, 77))} {tk_decl_value(assign(.assign, 0, 78))} {tk_decl_value(fresh(.call))}")
    # A scan's kind.
    loop open in [false, true]:
        loop d in [false, true]:
            loop p in [false, true]:
                tks = TkScan(open=open, d_direct=d, p_direct=p)
                print(tk_own_kind())
    # Candidates.
    print("{tk_candidate(vardecl(1, temp(1, CELSIUS)))} {tk_candidate(vardecl(1, temp(1, KELVIN)))} {tk_candidate(vardecl(1, ilit(1)))} {tk_candidate(assign(.assign, ident(1), temp(1, CELSIUS)))}")
    typed = vardecl(1, temp(1, CELSIUS)); nodes[typed].a = 1
    many = vardecl(1, temp(1, CELSIUS)); node_set_list(mut nodes, mut lists, many, [ident(1)])
    print("{tk_candidate(typed)} {tk_candidate(many)}")
    known = vardecl(1, ilit(1)); tk_direct[known] = 3
    deciding = vardecl(1, ilit(1)); tk_deciding[deciding] = true
    print("{tk_candidate(known)} {tk_candidate(deciding)}")
    # Partners: unmediated, cached, in progress, block and module scopes.
    reset_scan()
    tks.mediate = false
    print(tk_partner(vardecl(1, temp(1, CELSIUS)), 0, 0))
    reset_scan()
    d1 = vardecl(60, temp(1, CELSIUS))
    tk_direct[d1] = 3
    print(tk_partner(d1, 0, 0))
    d2 = vardecl(60, temp(1, CELSIUS))
    tk_deciding[d2] = true
    print(tk_partner(d2, 1, 0))
    tk_deciding.clear()
    print(tk_partner(vardecl(60, temp(1, CELSIUS)), 0, 0))
    scoped = vardecl(60, temp(1, CELSIUS))
    uses = block([scoped, bin(.star, ident(60), ilit(2))])
    keep = tks.name
    print("{tk_partner(scoped, uses, 0)} {tks.name == keep} {tk_decls.len()} {tk_direct.has(scoped)}")
    d3 = vardecl(61, temp(1, CELSIUS))
    nodes[d3].flags = i32(NF_GLOBAL); nodes[d3].mod = 0
    modules[0].decls = [d3, fresh(.fn_)]
    modules[0].inits = [d3, bin(.minus, ident(61), checked(ident(1), T_POINT))]
    print(tk_partner(d3, 0, 0))
    print(tk_decided(d3, T_DELTA))
    undecided = vardecl(62, temp(1, CELSIUS))
    print("{tk_decided(undecided, T_DELTA)} {tk_decided(undecided, T_POINT)}")
    modules[0].decls = []; modules[0].inits = []
    # Operand classes.
    reset_scan()
    loop x in [0, checked(ident(1), T_DELTA), checked(ident(1), 0), temp(1, CELSIUS), temp(1, KELVIN), ilit(1), flit(1.0), fresh(.str_lit), fresh(.bool_lit), fresh(.none_lit), neg(checked(ident(1), T_DELTA)), neg(ilit(1)), fresh(.call), fresh(.field), fresh(.index), fresh(.if_), fresh(.match_), fresh(.block), fresh(.tuple)]:
        print("c {tk_class(x, 0)}")
    print(tk_class(ilit(1), 7))
    un = fresh(.unary); nodes[un].op = i32(int(Tok.tilde)); nodes[un].a = i32(checked(ident(1), T_DELTA))
    print(tk_class(un, 0))
    loop inner in [checked(ident(1), T_DELTA), temp(1, CELSIUS), ident(50), checked(ident(1), T_POINT)]:
        c = fresh(.cast); nodes[c].a = i32(inner)
        print("cast {tk_class(c, 0)}")
    operands = [checked(ident(1), T_POINT), checked(ident(1), T_DELTA), temp(1, CELSIUS), ident(50), ilit(1)]
    loop op in [Tok.plus, Tok.minus]:
        loop a in operands:
            row = ""
            loop b in operands: row = "{row} {tk_class(bin(op, a, b), 0)}"
            print(row)
    loop a in operands:
        row = ""
        loop b in operands: row = "{row} {tk_class(bin(.star, a, b), 0)} {tk_class(bin(.slash, a, b), 0)}"
        print(row)
    print("{tk_class(bin(.star, ilit(2), ident(CELSIUS)), 0)} {tk_class(bin(.star, ident(9), ident(CELSIUS)), 0)} {tk_class(bin(.star, ident(9), checked(ident(CELSIUS), T_POINT)), 0)} {tk_class(bin(.star, flit(2.0), checked(ident(1), T_DELTA)), 0)} {tk_class(bin(.slash, flit(2.0), checked(ident(1), T_DELTA)), 0)} {tk_class(bin(.percent, ilit(2), ilit(2)), 0)}")
    print("{tk_operand_class(ident(50), 0)} {tk_operand_class(checked(ident(1), T_DELTA), 0)}")
    # Identifier classes: in the walk's scope, this binding, scope lookups.
    reset_scan()
    tk_decls = [TkDecl(80, 0, 0, 0)]
    plain_value = vardecl(81, checked(ident(1), T_DELTA))
    candidate = vardecl(82, temp(1, CELSIUS))
    tk_direct[candidate] = 2
    tk_decls.push(TkDecl(81, plain_value, 0, 0))
    tk_decls.push(TkDecl(82, candidate, 0, 0))
    loop nm in [80, 81, 82, 50, 83]: print("id {tk_ident_class(ident(nm), 0)}")
    reset_scan()
    l_delta = bind_local(84, T_DELTA)
    l_bound = bind_local(85, T_POINT)
    bound_decl = vardecl(85, temp(1, CELSIUS))
    tk_direct[bound_decl] = 3
    tk_bindings[l_bound] = bound_decl
    cap = bind_local(86, T_INT)
    locals[cap].flags = i32(LF_CAPTURE); locals[cap].outer = i32(l_bound)
    cap2 = bind_local(87, T_DELTA)
    locals[cap2].flags = i32(LF_CAPTURE)
    print("{l_delta} {cap2}")
    syms.push(Sym(kind=.fns)); scope[88] = syms.len() - 1
    gd = vardecl(90, checked(ident(1), T_DELTA))
    bg = bind_global(89, T_POINT, 2, gd)
    tk_bindings[-bg - 1] = bound_decl
    bind_global(90, T_DELTA, 2, gd)
    self_decl = vardecl(91, ilit(1))
    bind_global(91, T_POINT, 0, self_decl)
    const_g = bind_global(92, T_POINT, 0, gd)
    globals[const_g].is_const = true
    cand_g_decl = vardecl(93, temp(1, CELSIUS))
    tk_direct[cand_g_decl] = 2
    bind_global(93, T_POINT, 0, cand_g_decl)
    bind_global(94, T_POINT, 0, gd)
    tks.self_decl = self_decl
    loop nm in [84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94]:
        print("id {nm} {tk_ident_class(ident(nm), 0)} other {tk_other(ident(nm))} mediated {tk_other_mediated}")
    tk_decls = [TkDecl(95, 0, 0, 0), TkDecl(96, candidate, 0, 0)]
    loop x in [ident(95), ident(96), checked(ident(96), T_POINT), temp(1, CELSIUS)]: print("other {tk_other(x)} {tk_other_mediated}")
    # Uses.
    point = () -> int: checked(ident(1), T_POINT)
    delta = () -> int: checked(ident(1), T_DELTA)
    use_at(bin(.plus, me(), me()))
    use_at(bin(.plus, ident(1), ident(2)))
    loop op in [Tok.plus, Tok.minus, Tok.star, Tok.slash, Tok.eq, Tok.ne, Tok.lt, Tok.le, Tok.gt, Tok.ge, Tok.percent]:
        loop other in [point(), delta(), ilit(2)]:
            use_at(bin(op, me(), other))
            use_at(bin(op, other, me()))
    loop c in [43, 45, 42, 47, 37]:
        use_at(dot(c, me(), point()))
        use_at(dot(c, point(), me()))
    use_at(bin(.slash, me(), ident(CELSIUS)))
    use_at(neg(me()))
    use_at(neg(point()))
    no_minus = fresh(.unary); nodes[no_minus].op = i32(int(Tok.plus)); nodes[no_minus].a = i32(me())
    use_at(no_minus)
    use_at(assign(.assign, me(), temp(1, CELSIUS)))
    use_at(assign(.assign, me(), temp(1, KELVIN)))
    use_at(assign(.pluseq, me(), temp(1, CELSIUS)))
    use_at(assign(.pluseq, point(), me()))
    use_at(assign(.minuseq, delta(), me()))
    use_at(assign(.pluseq, ilit(1), me()))
    use_at(assign(.stareq, point(), me()))
    use_at(assign(.assign, point(), ilit(1)))
    use_at(fresh(.call))
    # Notes.
    reset_scan()
    tk_note(true, 1, 2, true); tk_note(true, 3, 4, false); tk_note(false, 5, 6, true); tk_note(false, 7, 8, false)
    print(show())
    # Walks: scoping forms, declarations, nested uses.
    walk_at(0)
    walk_at(checked(bin(.plus, me(), point()), 1))
    walk_at(me())
    mine = me(); nodes[mine].flags = i32(NF_AT)
    walk_at(mine)
    mine2 = me(); nodes[mine2].flags = i32(NF_MUT)
    walk_at(mine2)
    other_at = ident(2); nodes[other_at].flags = i32(NF_AT)
    walk_at(other_at)
    walk_at(block([bin(.plus, me(), point()), neg(me())]))
    walk_at(block([vardecl(50, ilit(1)), neg(me())]))
    p = fresh(.param); nodes[p].name = 50; nodes[p].b = i32(neg(me()))
    lam = fresh(.lambda); node_set_list(mut nodes, mut lists, lam, [p, ident(1)]); nodes[lam].b = i32(neg(me()))
    walk_at(lam)
    fun = fresh(.fn_); nodes[fun].b = i32(neg(me()))
    walk_at(fun)
    loop_var = fresh(.for_); nodes[loop_var].a = i32(neg(me())); node_set_list(mut nodes, mut lists, loop_var, [ident(50), neg(me())]); nodes[loop_var].b = i32(neg(me()))
    walk_at(loop_var)
    walk_at(vardecl(52, neg(me())))
    tuple_decl = vardecl(52, neg(me())); node_set_list(mut nodes, mut lists, tuple_decl, [ident(53), fresh(.call)])
    walk_at(tuple_decl)
    walk_at(assign(.assign, ident(54), neg(me())))
    walk_at(assign(.assign, ident(CELSIUS), neg(me())))
    walk_at(assign(.assign, me(), temp(1, CELSIUS)))
    walk_at(assign(.pluseq, ident(54), neg(me())))
    children = fresh(.if_); nodes[children].a = i32(neg(me())); nodes[children].b = i32(neg(me())); nodes[children].c = i32(neg(me())); nodes[children].d = i32(neg(me()))
    walk_at(children)
    second = fresh(.match_); nodes[second].list2 = i32(lists2.len()); nodes[second].nlist2 = 1; lists2.push(i32(neg(me())))
    walk_at(second)
    # A declaration statement remembers its place; the binding's own declaration is skipped.
    reset_scan()
    st_decl = vardecl(55, ilit(1))
    own = vardecl(50, ilit(1))
    two = fresh(.block)
    node_set_list(mut nodes, mut lists, two, [own, st_decl, assign(.assign, ident(56), ilit(1))])
    tks.self_decl = own
    loop i in [0..3): tk_statement(two, i)
    loop d in tk_decls: print("{d.name} {d.decl == st_decl} {d.block == two} {d.index}")
    # Text.
    loop x in [ident(1), temp(5, CELSIUS), bin(.star, flit(2.5), ident(CELSIUS)), neg(temp(5, CELSIUS)), fresh(.call)]: print(tk_text(x))
    loop op in [Tok.plus, Tok.minus, Tok.star, Tok.slash, Tok.eq, Tok.ne, Tok.lt, Tok.le, Tok.gt, Tok.ge, Tok.pluseq, Tok.minuseq, Tok.percent]: print(tk_op_text(op))
    print(tk_use_text(neg(ident(1))))
    print(tk_use_text(bin(.plus, ident(1), temp(2, CELSIUS))))
    loop c in [43, 45, 42, 47]: print(tk_use_text(dot(c, ident(1), ident(2))))
    print(tk_use_text(assign(.pluseq, ident(1), ident(2))))
    # A whole binding: refusals, ambiguous, conflict, difference, global.
    binding = (rest: int[], global: bool) -> int:
        reset_scan()
        tk_difference_reads = {}
        tk_difference_writes = {}
        tk_reads_on = false
        value = checked(temp(20, CELSIUS), T_POINT)
        s = vardecl(50, value)
        sibling_block = block([s] + rest)
        sibling_index = 0
        nodes[s].flags = 0
        r = temperature_binding(s, T_POINT, CELSIUS, global)
        print("binding {r} {show()} reads {tk_difference_reads.len()} on {tk_reads_on} writes {tk_difference_writes.len()} watch {statement_watch.temperature_writes} direct {tk_direct[s]} rewritten {nodes[s].b != value}")
        s
    print(temperature_binding(vardecl(50, ilit(1)), T_DELTA, CELSIUS, false))
    print(temperature_binding(vardecl(50, ilit(1)), T_NO_ORIGIN, CELSIUS, false))
    sibling_block = 0
    print(temperature_binding(vardecl(50, ilit(1)), T_POINT, CELSIUS, false))
    sibling_block = block([ilit(1)]); sibling_index = 4
    print(temperature_binding(vardecl(50, ilit(1)), T_POINT, CELSIUS, false))
    sibling_index = 0
    print(temperature_binding(vardecl(50, ilit(1)), T_POINT, CELSIUS, false))
    tail_decl = vardecl(50, ilit(1))
    sibling_block = block([tail_decl])
    print(temperature_binding(tail_decl, T_POINT, KELVIN, false))
    binding([], false)
    binding([bin(.minus, point(), me())], false)
    binding([bin(.minus, me(), point())], false)
    binding([bin(.plus, me(), point())], false)
    binding([bin(.plus, me(), point()), assign(.assign, me(), temp(3, CELSIUS))], false)
    binding([assign(.assign, me(), ilit(3)), bin(.plus, me(), point())], false)
    binding([neg(me()), bin(.minus, me(), point())], false)
    binding([bin(.star, me(), ilit(2)), bin(.lt, me(), point())], false)
    decl = vardecl(50, checked(temp(20, CELSIUS), T_POINT))
    nodes[decl].mod = 0
    modules[0].decls = [decl, fresh(.fn_)]
    modules[0].inits = [decl, neg(me())]
    reset_scan()
    print("global {temperature_binding(decl, T_POINT, CELSIUS, true)} {show()} {tk_direct[decl]}")
    # Reading a point as a difference.
    read = (t: int) -> int:
        n = fresh(.ident)
        nodes[n].type = i32(t)
        n
    r1 = read(T_POINT)
    print("{temperature_difference(r1) == r1} {last_checked == r1}")
    r2 = read(T_NO_ORIGIN)
    print(temperature_difference(r2) != r2)
    r3 = read(T_POINT)
    print("{temperature_difference_at(r3)} {last_checked == r3} {nodes[r3].kind == .ident}")
    r4 = read(T_POINT)
    print(temperature_read(r4, T_POINT))
    tk_difference_reads[r4] = true
    print(temperature_read(r4, T_DELTA))
    print(temperature_read(r4, T_POINT))
    r5 = read(T_POINT)
    print(temperature_write(r5, r5, T_POINT, T_DELTA))
    tk_difference_writes[r5] = true
    print(temperature_write(r5, r5, T_POINT, T_POINT))
    print(temperature_write(r5, r5, T_DELTA, T_DELTA))
    print(temperature_write(r5, r5, T_POINT, T_DELTA))
    print("temperature ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_temperature_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/temperature_kinds.jo').read_text()
    state = state[state.index('const TKC_OTHER'):]
    output = compare_narrow(compiler, tmp_path, release,
                            ('checker_tokens', 'node_store', 'checker_types', 'checker_state', 'temperature_ops'), DRIVER,
                            doubles={'services.jo': SERVICES, 'temperature_kinds.jo': state},
                            services=('ast', 'check', 'checker_expr', 'checked_eval', 'expr', 'frontend', 'lex', 'sibling_types', 'types', 'units', 'unit_ops', 'util'))
    assert output.endswith(b'temperature ok\n')
    for text in (b'leaves `n50` ambiguous', b'they disagree', b'force ', b'retag ', b'intern_tag 71'):
        assert text in output, text
