"""Byte scan loops: shape recognition, predicate domains, ranges and emitted calls match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'ir_types.dewy'
const LF_MUTPARAM = 1
const LF_CAPTURE = 2
const LF_ALIAS = 4
const LF_BYREF = 8
const LF_ADDR = 16
const LF_SHARED = 32
const LF_SOAELEM = 64
const LF_ELEMALIAS = 128
const VI = 0
const T_INT = 1
const T_U8 = 2
const T_ARRAY = 3
const T_STR = 4
const T_WIDE_ARRAY = 5
const T_TABLE = 6
const T_SHORT_TABLE = 7
const T_OTHER_TABLE = 8
const T_I8 = 9
const T_I4 = 10
const T_U16 = 11
const T_FLOAT = 12
enum CV: none_, int_, fixed_store
enum IN: other, len
struct Val:
    v: int
    owned: bool
    slot: int
struct Place:
    mem: bool
    v: int
nodes: Node[] = [Node()]
lists: i32[]
locals: Local[] = [Local()]
globals: Global[] = [Global()]
types: TypeInfo[] = [TypeInfo(), TypeInfo(kind=.int_, bits=64, sign=true), TypeInfo(kind=.int_, bits=8), TypeInfo(kind=.array, elem=2), TypeInfo(kind=.str_), TypeInfo(kind=.array, elem=1),
                     TypeInfo(kind=.fixed, bits=256, elem=2), TypeInfo(kind=.fixed, bits=16, elem=2), TypeInfo(kind=.fixed, bits=256, elem=1), TypeInfo(kind=.int_, bits=8, sign=true), TypeInfo(kind=.int_, bits=4), TypeInfo(kind=.int_, bits=16), TypeInfo(kind=.float_, bits=64)]
target_arm64 = false
target_wasm = false
dbg_on = false
fused_on = false
rodata: u8[]
ro_starts: int[]
next_vreg = 100
writable: {int: bool} = {}
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
ntype = (n: int) -> int: int(nodes[n].type)
prune = (t: int) -> int: t
tkind = (t: int) -> TK: types[t].kind
fixed_len = (t: int) -> int: int(types[t].bits)
readonly_global = (g: int) -> bool: not writable.has(g)
cx_token = (x: int) -> Tok: x as Tok
fz_note_raw = (o: int, align: int): print("fz_note_raw {o} {align}")
fresh_reg = () -> int:
    next_vreg += 1
    next_vreg
vreg = (ty: int) -> int:
    r = fresh_reg()
    print("vreg {ty} = {r}")
    r
e_iconst = (v: int) -> int:
    r = fresh_reg()
    print("iconst {v} = {r}")
    r
e_addi = (a: int, k: int) -> int:
    r = fresh_reg()
    print("addi {a} {k} = {r}")
    r
e_bin = (op: Op, ty: int, a: int, b: int) -> int:
    r = fresh_reg()
    print("bin {int(op)} {ty} {a} {b} = {r}")
    r
emit = (op: Op, ty: int, dst: int, a: int, b: int, c: int, imm: int) -> int:
    print("emit {int(op)} {ty} {dst} {a} {b} {c} {imm}")
    dst
stmt_begin = (): print("stmt_begin")
stmt_end = (): print("stmt_end")
iff = (c: int): print("iff {c}")
els = (): print("els")
endc = (): print("endc")
arr_len = (p: int) -> int:
    r = fresh_reg()
    print("arr_len {p} = {r}")
    r
gen_expr = (e: int) -> Val:
    r = fresh_reg()
    print("gen_expr {e} = {r}")
    Val(r, false, 0)
gen_borrowed = (e: int) -> Val:
    r = fresh_reg()
    print("gen_borrowed {e} = {r}")
    Val(r, false, 0)
gen_while_scalar = (s: int): print("gen_while_scalar {s}")
local_place = (l: int, write: bool) -> Place:
    print("local_place {l} {write}")
    Place(false, l)
write_place = (p: Place, t: int, v: int): print("write_place {p.v} {t} {v}")
'''

DRIVER = r'''
fresh = (k: NK, t: int) -> int:
    nodes.push(Node(kind=k, pos=nodes.len(), type=i32(t)))
    nodes.len() - 1
local = (flags: int) -> int:
    locals.push(Local(flags=i32(flags), offset=-1))
    locals.len() - 1
var = (l: int, t: int) -> int:
    n = fresh(.ident, t)
    nodes[n].aux = 1; nodes[n].sym = i32(l)
    n
lit = (v: int, t: int) -> int:
    n = fresh(.int_lit, t)
    nodes[n].ival = v
    n
bin = (op: Tok, a: int, b: int, t: int) -> int:
    n = fresh(.binary, t)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
both = (k: NK, a: int, b: int) -> int:
    n = fresh(k, 0)
    nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
neg = (a: int) -> int:
    n = fresh(.not_, 0)
    nodes[n].a = i32(a)
    n
conv = (a: int, t: int, cv: CV) -> int:
    n = fresh(.conv, t)
    nodes[n].a = i32(a); nodes[n].aux = i32(int(cv))
    n
seq = (items: int[]) -> int:
    n = fresh(.block, 0)
    node_set_list(mut nodes, mut lists, n, items)
    n
assign = (op: Tok, target: int, value: int) -> int:
    n = fresh(.assign, 0)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(target); nodes[n].b = i32(value)
    n
index = (base: int, ix: int, t: int) -> int:
    n = fresh(.index, t)
    nodes[n].a = i32(base); nodes[n].b = i32(ix)
    n
while_of = (cond: int, body: int) -> int:
    n = fresh(.while_, 0)
    nodes[n].a = i32(cond); nodes[n].b = i32(body)
    n
if_of = (cond: int, then_body: int) -> int:
    n = fresh(.if_, 0)
    nodes[n].a = i32(cond); nodes[n].b = i32(then_body)
    n
bytes_row = (b: u8[], from: int) -> str:
    s = ""
    loop j in [from..b.len()): s = "{s} {int(b[j])}"
    s
try_scan = (label: str, s: int):
    before = rodata.len()
    print("--- {label}")
    print(gen_scan_loop(s))
    print("rodata {bytes_row(rodata, before)} {ro_starts.len()}")
step = (l: int) -> int: assign(.pluseq, var(l, T_INT), lit(1, T_INT))
stop_lt = (l: int, stop: int) -> int: bin(.lt, var(l, T_INT), stop, 0)
domain_row = (d: int[]) -> str:
    s = ""
    loop x in d: s = "{s}{x},"
    "{d.len()}:{s}"
global_table = (values: int[], t: int, kind: SK) -> int:
    init = seq([])
    nodes[init].kind = .array
    items: int[]
    loop v in values: items.push(lit(v, T_U8))
    node_set_list(mut nodes, mut lists, init, items)
    globals.push(Global(is_const=true, init=i32(init)))
    n = fresh(.ident, t)
    nodes[n].aux = i32(int(kind)); nodes[n].sym = i32(globals.len() - 1)
    n
main = ():
    i = local(0); n = local(0); c = local(0); a = local(0); s = local(0); count = local(0); wide = local(0)
    iv = () -> int: var(i, T_INT)
    nv = () -> int: var(n, T_INT)
    cv = () -> int: var(c, T_U8)
    av = () -> int: var(a, T_ARRAY)
    sv = () -> int: var(s, T_STR)
    # scan_local, scan_word, scan_inc, scan_value, scan_bound.
    print("{scan_local(0)} {scan_local(lit(1, T_INT))} {scan_local(iv())}")
    other_sk = iv(); nodes[other_sk].aux = 2
    print(scan_local(other_sk))
    loop f in [1, 2, 4, 8, 16, 32, 64, 128, 256]: print("flag {f} {scan_local(var(local(f), T_INT)) > 0}")
    stored = local(0); locals[stored].offset = 8
    print(scan_local(var(stored, T_INT)))
    print("{scan_word(iv())} {scan_word(cv())}")
    loop x in [step(i), step(n), assign(.pluseq, iv(), lit(2, T_INT)), assign(.pluseq, iv(), nv()), assign(.minuseq, iv(), lit(1, T_INT)), assign(.assign, iv(), bin(.plus, iv(), lit(1, T_INT), T_INT)),
               assign(.assign, iv(), conv(bin(.plus, iv(), lit(1, T_INT), T_INT), T_INT, CV.fixed_store)), assign(.assign, iv(), conv(bin(.plus, iv(), lit(1, T_INT), T_INT), T_INT, CV.int_)),
               assign(.assign, iv(), bin(.minus, iv(), lit(1, T_INT), T_INT)), assign(.assign, iv(), bin(.plus, nv(), lit(1, T_INT), T_INT)), assign(.assign, iv(), bin(.plus, iv(), lit(2, T_INT), T_INT)),
               assign(.assign, iv(), bin(.plus, iv(), nv(), T_INT)), assign(.assign, iv(), lit(1, T_INT)), seq([])]:
        print(scan_inc(x, i))
    print("{scan_value(lit(1, T_INT), i)} {scan_value(iv(), i)} {scan_value(nv(), i)} {scan_value(fresh(.call, T_INT), i)}")
    length = fresh(.intrinsic, T_INT); nodes[length].aux = i32(int(IN.len)); node_set_list(mut nodes, mut lists, length, [av()])
    other_in = fresh(.intrinsic, T_INT); nodes[other_in].aux = i32(int(IN.other)); node_set_list(mut nodes, mut lists, other_in, [av()])
    two_kids = fresh(.intrinsic, T_INT); nodes[two_kids].aux = i32(int(IN.len)); node_set_list(mut nodes, mut lists, two_kids, [av(), av()])
    computed = fresh(.intrinsic, T_INT); nodes[computed].aux = i32(int(IN.len)); node_set_list(mut nodes, mut lists, computed, [fresh(.call, T_ARRAY)])
    print("{scan_bound(nv(), i)} {scan_bound(cv(), i)} {scan_bound(iv(), i)} {scan_bound(length, i)} {scan_bound(other_in, i)} {scan_bound(two_kids, i)} {scan_bound(computed, i)}")
    # Literals, tables and domains over every expression form.
    u8lit = lit(200, T_U8)
    print("{scan_literal(u8lit)} {scan_literal(lit(256, T_INT))} {scan_literal(lit(-1, T_INT))} {scan_literal(iv())} {scan_literal(conv(u8lit, T_INT, CV.int_))} {scan_literal(conv(conv(u8lit, T_U16, CV.int_), T_INT, CV.int_))}")
    print("{scan_literal(conv(u8lit, T_I8, CV.int_))} {scan_literal(conv(u8lit, T_I4, CV.int_))} {scan_literal(conv(u8lit, T_FLOAT, CV.int_))} {scan_literal(conv(u8lit, T_INT, CV.fixed_store))} {scan_literal(conv(u8lit, T_U8, CV.int_))}")
    values: int[]
    loop v in [0..256): values.push(if v >= 128: 1 else: 0)
    table = global_table(values, T_TABLE, SK.const_)
    print(scan_table(table) != 0)
    variant = global_table(values, T_TABLE, SK.global)
    print(scan_table(variant) != 0)
    g = int(nodes[variant].sym)
    globals[g].is_const = false
    print(scan_table(variant) != 0)
    writable[g] = true
    print(scan_table(variant) != 0)
    writable.clear()
    globals[g].fn_written = true
    print(scan_table(variant) != 0)
    globals[g].fn_written = false; globals[g].init_written = true
    print(scan_table(variant) != 0)
    globals[g].init_written = false; globals[g].exposed = true
    print(scan_table(variant) != 0)
    globals[g].exposed = false
    decl = fresh(.vardecl, 0); nodes[decl].b = globals[g].init
    globals[g].init = 0; globals[g].decl = i32(decl)
    print(scan_table(variant) != 0)
    print("{scan_table(iv()) != 0} {scan_table(global_table(values, T_SHORT_TABLE, SK.const_)) != 0} {scan_table(global_table(values, T_OTHER_TABLE, SK.const_)) != 0} {scan_table(global_table(values, T_FLOAT, SK.const_)) != 0} {scan_table(global_table([1, 2], T_TABLE, SK.const_)) != 0}")
    byte = () -> int: index(av(), iv(), T_U8)
    bound = stop_lt(i, nv())
    forms = [bound, lit(7, T_U8), byte(), index(sv(), iv(), T_U8), index(av(), nv(), T_U8), index(fresh(.call, T_ARRAY), iv(), T_U8), index(var(wide, T_WIDE_ARRAY), iv(), T_INT), index(var(local(0), T_INT), iv(), T_U8),
             index(table, byte(), T_U8), index(table, iv(), T_U8), index(table, bin(.star, byte(), lit(2, T_INT), T_INT), T_U8), index(iv(), byte(), T_U8), index(global_table(fill(300, 256), T_TABLE, SK.const_), byte(), T_U8),
             conv(byte(), T_INT, CV.int_), conv(byte(), T_U8, CV.int_), conv(byte(), T_U16, CV.int_), conv(iv(), T_INT, CV.int_), conv(byte(), T_INT, CV.fixed_store),
             neg(byte()), neg(fresh(.call, 0)), fresh(.call, T_INT)]
    loop op in [Tok.amp, Tok.eq, Tok.ne, Tok.lt, Tok.le, Tok.gt, Tok.ge, Tok.plus]: forms.push(bin(op, byte(), lit(65, T_U8), T_U8))
    aux_form = bin(.eq, byte(), lit(1, T_U8), 0); nodes[aux_form].aux = 2
    forms.push(aux_form)
    forms.push(both(.and_, bin(.ge, byte(), lit(48, T_U8), 0), bin(.le, byte(), lit(57, T_U8), 0)))
    forms.push(both(.or_, bin(.lt, byte(), lit(48, T_U8), 0), bin(.gt, byte(), lit(57, T_U8), 0)))
    forms.push(both(.or_, fresh(.call, 0), byte()))
    forms.push(both(.or_, byte(), fresh(.call, 0)))
    forms.push(both(.and_, index(av(), iv(), T_U8), index(sv(), iv(), T_U8)))
    deep = byte()
    loop j in [0..30): deep = neg(deep)
    forms.push(deep)
    loop form in forms:
        state = [0, 0, bound]
        d = scan_domain(form, i, mut state)
        print("{domain_row(d)} {state[0]} {state[1] != 0}")
    # Ranges, both truths.
    alternating: int[]
    loop v in [0..256): alternating.push(v % 2)
    tail: int[]
    loop v in [0..256): tail.push(if v == 255 or v == 7: 3 else: 0)
    loop d in [values, alternating, tail, fill(0, 256), fill(1, 256)]:
        print(scan_ranges(d, true).len())
        print(bytes_row(scan_ranges(d, false), max(0, scan_ranges(d, false).len() - 8)))
    # The loop: everything that blocks it.
    good = () -> int: while_of(both(.and_, stop_lt(i, nv()), bin(.ne, byte(), cv(), 0)), seq([step(i)]))
    dbg_on = true
    print(gen_scan_loop(good()))
    dbg_on = false; target_arm64 = true
    print(gen_scan_loop(good()))
    target_arm64 = false; target_wasm = true
    print(gen_scan_loop(good()))
    target_wasm = false
    with_aux = good(); nodes[with_aux].aux = 1
    print(gen_scan_loop(with_aux))
    try_scan("no body", while_of(stop_lt(i, nv()), seq([])))
    try_scan("no predicate", while_of(stop_lt(i, nv()), seq([step(i)])))
    try_scan("three", while_of(stop_lt(i, nv()), seq([step(i), step(i), step(i)])))
    try_scan("not if", while_of(stop_lt(i, nv()), seq([step(i), step(i)])))
    if_with_else = if_of(bin(.eq, byte(), cv(), 0), seq([step(count)])); nodes[if_with_else].c = i32(seq([]))
    try_scan("else", while_of(stop_lt(i, nv()), seq([if_with_else, step(i)])))
    try_scan("two then", while_of(stop_lt(i, nv()), seq([if_of(bin(.eq, byte(), cv(), 0), seq([step(count), step(count)])), step(i)])))
    try_scan("not update", while_of(stop_lt(i, nv()), seq([if_of(bin(.eq, byte(), cv(), 0), seq([seq([])])), step(i)])))
    try_scan("bad counter", while_of(stop_lt(i, nv()), seq([if_of(bin(.eq, byte(), cv(), 0), seq([assign(.pluseq, fresh(.call, T_INT), lit(1, T_INT))])), step(i)])))
    try_scan("byte counter", while_of(stop_lt(i, nv()), seq([if_of(bin(.eq, byte(), cv(), 0), seq([assign(.pluseq, cv(), lit(1, T_U8))])), step(i)])))
    try_scan("by two", while_of(stop_lt(i, nv()), seq([if_of(bin(.eq, byte(), cv(), 0), seq([assign(.pluseq, var(count, T_INT), lit(2, T_INT))])), step(i)])))
    try_scan("not lt", while_of(both(.and_, bin(.le, iv(), nv(), 0), bin(.ne, byte(), cv(), 0)), seq([step(i)])))
    not_binary = both(.and_, fresh(.call, 0), bin(.ne, byte(), cv(), 0))
    try_scan("no bound", while_of(not_binary, seq([step(i)])))
    aux_bound = stop_lt(i, nv()); nodes[aux_bound].aux = 1
    try_scan("aux bound", while_of(both(.and_, aux_bound, bin(.ne, byte(), cv(), 0)), seq([step(i)])))
    try_scan("bad index", while_of(both(.and_, bin(.lt, lit(1, T_INT), nv(), 0), bin(.ne, byte(), cv(), 0)), seq([step(i)])))
    try_scan("byte index", while_of(both(.and_, bin(.lt, var(i, T_U8), nv(), 0), bin(.ne, byte(), cv(), 0)), seq([step(i)])))
    try_scan("self stop", while_of(both(.and_, bin(.lt, iv(), iv(), 0), bin(.ne, byte(), cv(), 0)), seq([step(i)])))
    try_scan("other step", while_of(both(.and_, stop_lt(i, nv()), bin(.ne, byte(), cv(), 0)), seq([step(n)])))
    try_scan("counter is index", while_of(stop_lt(i, nv()), seq([if_of(bin(.eq, byte(), cv(), 0), seq([step(i)])), step(i)])))
    try_scan("counter is stop", while_of(stop_lt(i, nv()), seq([if_of(bin(.eq, byte(), cv(), 0), seq([step(n)])), step(i)])))
    # A found byte, each sense, with the bound's length and literal forms.
    try_scan("find ne", good())
    try_scan("find eq", while_of(both(.and_, stop_lt(i, nv()), bin(.eq, byte(), cv(), 0)), seq([step(i)])))
    try_scan("find not eq", while_of(both(.and_, stop_lt(i, nv()), neg(bin(.eq, byte(), cv(), 0))), seq([step(i)])))
    try_scan("find not ne", while_of(both(.and_, stop_lt(i, nv()), neg(bin(.ne, byte(), cv(), 0))), seq([step(i)])))
    try_scan("find literal", while_of(both(.and_, stop_lt(i, length), bin(.ne, byte(), lit(10, T_U8), 0)), seq([step(i)])))
    try_scan("in text", while_of(both(.and_, stop_lt(i, lit(10, T_INT)), bin(.ne, index(sv(), iv(), T_U8), cv(), 0)), seq([step(i)])))
    try_scan("wide array", while_of(both(.and_, stop_lt(i, nv()), bin(.ne, index(var(wide, T_WIDE_ARRAY), iv(), T_U8), cv(), 0)), seq([step(i)])))
    try_scan("float base", while_of(both(.and_, stop_lt(i, nv()), bin(.ne, index(var(local(0), T_FLOAT), iv(), T_U8), cv(), 0)), seq([step(i)])))
    try_scan("computed base", while_of(both(.and_, stop_lt(i, nv()), bin(.ne, index(fresh(.call, T_ARRAY), iv(), T_U8), cv(), 0)), seq([step(i)])))
    try_scan("needle is index", while_of(both(.and_, stop_lt(i, nv()), bin(.ne, byte(), var(i, T_U8), 0)), seq([step(i)])))
    # Counting, each sense, and a counter that is also the needle.
    tally = (cond: int) -> int: while_of(stop_lt(i, nv()), seq([if_of(cond, seq([step(count)])), step(i)]))
    try_scan("tally eq", tally(bin(.eq, byte(), cv(), 0)))
    try_scan("tally ne", tally(bin(.ne, byte(), cv(), 0)))
    try_scan("tally not", tally(neg(bin(.eq, byte(), cv(), 0))))
    try_scan("tally self", tally(bin(.eq, byte(), var(count, T_U8), 0)))
    # Byte classes: a run, its inverse, a table, too many ranges, nothing scanned, nested and.
    high = () -> int: bin(.ge, byte(), lit(128, T_U8), 0)
    try_scan("class", while_of(both(.and_, stop_lt(i, nv()), high()), seq([step(i)])))
    try_scan("class low", while_of(both(.and_, stop_lt(i, nv()), bin(.lt, byte(), lit(128, T_U8), 0)), seq([step(i)])))
    digit = () -> int: both(.and_, bin(.ge, byte(), lit(48, T_U8), 0), bin(.le, byte(), lit(57, T_U8), 0))
    try_scan("digits", while_of(both(.and_, stop_lt(i, nv()), digit()), seq([step(i)])))
    try_scan("tally digits", tally(digit()))
    try_scan("tally not digits", tally(neg(digit())))
    try_scan("table", while_of(both(.and_, stop_lt(i, nv()), index(table, byte(), T_U8)), seq([step(i)])))
    many = (bin(.amp, conv(byte(), T_INT, CV.int_), lit(16, T_INT), T_INT))
    try_scan("bit", while_of(both(.and_, stop_lt(i, nv()), many), seq([step(i)])))
    pieces = bin(.eq, byte(), lit(1, T_U8), 0)
    loop v in [3, 5, 7, 9, 11]: pieces = both(.or_, pieces, bin(.eq, byte(), lit(v, T_U8), 0))
    try_scan("too many", while_of(both(.and_, stop_lt(i, nv()), pieces), seq([step(i)])))
    try_scan("no byte", while_of(both(.and_, stop_lt(i, nv()), lit(1, T_U8)), seq([step(i)])))
    try_scan("unknown", while_of(both(.and_, stop_lt(i, nv()), fresh(.call, 0)), seq([step(i)])))
    # (`i < n and a and b` nests leftward: the whole condition is the predicate)
    nested = both(.and_, both(.and_, stop_lt(i, nv()), high()), bin(.lt, byte(), lit(240, T_U8), 0))
    try_scan("nested", while_of(nested, seq([step(i)])))
    too_deep = stop_lt(i, nv())
    loop j in [0..10): too_deep = both(.and_, too_deep, high())
    try_scan("too deep", while_of(too_deep, seq([step(i)])))
    fused_on = true
    try_scan("fused", while_of(both(.and_, stop_lt(i, nv()), high()), seq([step(i)])))
    print("scan ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_scanloops_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare_narrow(compiler, tmp_path, release,
                            ('node_store', 'checker_state', 'checker_types', 'checker_tokens', 'ir_types', 'scanloops'), DRIVER,
                            doubles={'services.jo': SERVICES},
                            services=('ast', 'check', 'checked_eval', 'expr', 'fused', 'ir', 'ir_builders', 'lower', 'lower_group', 'lower_storage', 'types'))
    assert output.endswith(b'scan ok\n')
    for text in (b'--- find ne\nstmt_begin', b'--- too many\nfalse', b'--- tally digits\nstmt_begin', b'fz_note_raw', b'gen_while_scalar'):
        assert text in output, text
