"""Juxtaposition: head classification, products, powers, hints and diagnostics match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'source_types.dewy'
const NF_CHECKED = 1
const NF_JUXT = 2
const NF_SPREAD = 4
const NF_EXCL_FIRST = 8
const AUX2_PARTIAL = -10
const T_INT = 1
const T_FLOAT = 2
const T_QUANTITY = 3
const T_REFINED = 4
const T_RATIONAL = 5
const T_WORD_RATIONAL = 6
const T_BIG = 7
const T_FN = 8
const T_CFN = 9
const T_POLY = 10
const T_CALLABLE = 11
const T_ARRAY = 12
const T_FIXED = 13
const T_VEC = 14
const T_ND = 15
const T_TEXT = 16
const T_MIXED = 17
const T_NUMS = 18
const T_FNS = 19
const T_POINT = 20
const T_POINTER = 21
const T_VAR = 22
const T_PARAM = 23
nodes: Node[] = [Node()]
lists: i32[]
syms: Sym[] = [Sym()]
locals: Local[] = [Local()]
globals: Global[] = [Global()]
files: SrcFile[] = [SrcFile(src="", is_dewy=false), SrcFile(src="", is_dewy=true)]
structs: StructInfo[] = [StructInfo(fields=0, nfields=2)]
fields: Field[] = [Field(name=70, type=1), Field(name=71, type=12)]
types: TypeInfo[] = [TypeInfo(), TypeInfo(kind=.int_), TypeInfo(kind=.float_), TypeInfo(kind=.quantity), TypeInfo(kind=.refined, elem=1), TypeInfo(kind=.struct_), TypeInfo(kind=.struct_), TypeInfo(kind=.struct_), TypeInfo(kind=.fn_), TypeInfo(kind=.cfn), TypeInfo(kind=.polyfn), TypeInfo(kind=.callable), TypeInfo(kind=.array), TypeInfo(kind=.fixed), TypeInfo(kind=.vec), TypeInfo(kind=.struct_, st=9), TypeInfo(kind=.str_),
                     TypeInfo(kind=.enum_), TypeInfo(kind=.enum_), TypeInfo(kind=.enum_), TypeInfo(kind=.struct_, st=0), TypeInfo(kind=.ptr, elem=20), TypeInfo(kind=.var), TypeInfo(kind=.param)]
scope: {int: int} = {}
functions: {int: bool} = {}
checked_type = 1
checked_grows = true
last_checked = 0
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
set_kid = (n: int, i: int, v: int): lists[int(nodes[n].list) + i] = i32(v)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
add_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) | f)
prune = (t: int) -> int: t
tkind = (t: int) -> TK: types[t].kind
is_union = (t: int) -> bool: t == T_MIXED or t == T_NUMS or t == T_FNS
union_members = (t: int) -> int[]:
    if t == T_MIXED: return [T_FN, T_INT]
    if t == T_NUMS: return [T_INT, T_FLOAT]
    [T_FN, T_TEXT]
is_nd = (t: int) -> bool: t == T_ND
bundled_rational_type = (t: int) -> bool: t == T_RATIONAL
bundled_word_rational_type = (t: int) -> bool: t == T_WORD_RATIONAL
bundled_bigint_type = (t: int) -> bool: t == T_BIG
dt = (t: int) -> str: "dt{t}"
a_type = (t: int) -> str: "a{t}"
name_of = (n: int) -> str:
    if n == 99: return "$end"
    if n == 98: return ""
    if n == 97: return "3.5"
    "n{n}"
lookup = (name: int) -> int: scope.get(name) ?? 0
ensure_global = (g: int, pos: int, in_flow: bool = false): print("ensure_global {g} {pos} {in_flow}")
check_struct_fields = (si: int): print("check_struct_fields {si}")
check_expr = (n: int, e: int) -> int:
    print("check_expr {n} {e}")
    last_checked = n
    if checked_grows:
        nodes.push(Node(kind=nodes[n].kind))
        last_checked = nodes.len() - 1
    checked_type
call_collect_fns = (name: int, out: mut int[]):
    if functions.has(name): out.push(name)
collect_fns = (name: int, out: *(int[])):
    if functions.has(name): out[0].push(name)
fatal = (pos: int, msg: str): print("fatal {pos}: {msg}")
warn = (pos: int, msg: str): print("warn {pos}: {msg}")
pos_file = (pos: int) -> int: pos >> 40
pos_off = (pos: int) -> int: pos & 0xFFFFFFFFFF
pos_in_lib = (pos: int) -> bool: pos >= 1 << 41
is_ident_char = (c: u8) -> bool: c == '_' or c >= 'a' and c <= 'z' or c >= 'A' and c <= 'Z' or c >= '0' and c <= '9'
'''

DRIVER = r'''
fresh = (k: NK) -> int:
    nodes.push(Node(kind=k, pos=nodes.len()))
    nodes.len() - 1
ident = (name: int) -> int:
    n = fresh(.ident)
    nodes[n].name = i32(name)
    n
lit = (v: int) -> int:
    n = fresh(.int_lit)
    nodes[n].ival = v
    n
field = (base: int, name: int) -> int:
    n = fresh(.field)
    nodes[n].a = i32(base); nodes[n].name = i32(name)
    n
call = (head: int, args: int[], flags: int) -> int:
    n = fresh(.call)
    nodes[n].a = i32(head); nodes[n].flags = i32(flags)
    node_set_list(mut nodes, mut lists, n, args)
    n
bind = (name: int, kind: SK, r: int):
    syms.push(Sym(kind=kind, ref=i32(r)))
    scope[name] = syms.len() - 1
local_of = (name: int, t: int):
    locals.push(Local(type=i32(t)))
    bind(name, .local, locals.len() - 1)
show = (n: int) -> str:
    x = nodes[n]
    "{x.kind == .binary}/{x.kind == .call} op={x.op} a={x.a} b={x.b} list={x.list != 0} nlist={x.nlist} sym={x.sym} aux={x.aux} aux2={x.aux2} flags={x.flags} pos={x.pos}"
at = (file: int, off: int) -> int: (file << 40) | off
main = ():
    # Numbers, callables, and the text of a head.
    loop t in [T_INT, T_FLOAT, T_QUANTITY, T_REFINED, T_RATIONAL, T_WORD_RATIONAL, T_BIG, T_FN, T_CFN, T_POLY, T_CALLABLE, T_ARRAY, T_TEXT, T_MIXED]:
        print("{t} {juxt_numeric(t)} {juxt_callable(t)}")
    x = ident(30)
    fx = field(x, 31)
    f0 = field(fresh(.call), 32)
    no_name = field(x, 0)
    fl = fresh(.float_lit); nodes[fl].sval = 97
    fl0 = fresh(.float_lit)
    arg_call = call(x, [ident(33), lit(2)], 0)
    three = call(x, [lit(1), lit(2), lit(3)], 0)
    of_call = call(arg_call, [lit(1)], 0)
    of_group = call(fresh(.binary), [lit(1)], 0)
    of_named = call(x, [fresh(.namedarg)], 0)
    index_of = call(x, [lit(1)], 0); nodes[index_of].kind = .index
    loop h in [x, fx, f0, no_name, lit(7), fl, fl0, arg_call, three, of_call, of_group, of_named, index_of, fresh(.binary)]:
        print(juxt_text(h))
    print(juxt_texts([], " "))
    print(juxt_texts([x, lit(1)], " * "))
    print(juxt_texts([x, fresh(.binary)], " * "))
    print(juxt_texts([fresh(.namedarg)], " * "))
    # A route's type: each binding kind, a struct's field, through a pointer, absent.
    local_of(40, T_INT)
    globals.push(Global(type=i32(T_FLOAT)))
    bind(41, .global, globals.len() - 1)
    bind(42, .const_, 0)
    bind(43, .fns, 0)
    local_of(44, T_POINT)
    local_of(45, T_POINTER)
    local_of(46, T_INT)
    route = (n: int): print("route {juxt_route_type(n)}")
    loop name in [40, 41, 42, 43, 49]: route(ident(name))
    route(field(ident(44), 70))
    route(field(ident(44), 71))
    route(field(ident(45), 70))
    route(field(ident(44), 72))
    route(field(ident(46), 70))
    route(field(ident(49), 70))
    with_b = field(ident(44), 70); nodes[with_b].b = 1
    route(with_b)
    route(lit(1))
    # Whether a marked call's head multiplies.
    head = (h: int, args: int[], flags: int): print("head {juxt_head_numeric(call(h, args, flags))}")
    head(ident(40), [lit(1)], 0)
    head(ident(40), [lit(1)], NF_JUXT | NF_CHECKED)
    head(ident(40), [], NF_JUXT)
    bare = call(0, [lit(1)], NF_JUXT)
    print(juxt_head_numeric(bare))
    other_kind = call(ident(40), [lit(1)], NF_JUXT); nodes[other_kind].kind = .index
    print(juxt_head_numeric(other_kind))
    head(field(ident(44), 70), [lit(1)], NF_JUXT)
    head(field(ident(44), 71), [lit(1)], NF_JUXT)
    head(field(ident(44), 72), [lit(1)], NF_JUXT)
    head(ident(40), [lit(1)], NF_JUXT)
    head(ident(49), [lit(1)], NF_JUXT)
    local_of(50, T_FN)
    head(ident(50), [lit(1)], NF_JUXT)
    local_of(99, T_INT)
    head(ident(99), [lit(1)], NF_JUXT)
    local_of(98, T_INT)
    head(ident(98), [lit(1)], NF_JUXT)
    loop t in [T_MIXED, T_NUMS, T_FNS, T_ARRAY, T_FIXED, T_VEC, T_ND, T_TEXT]:
        local_of(60, t)
        head(ident(60), [lit(1)], NF_JUXT)
    # A group head: its checked value decides, and replaces the head.
    loop t in [T_INT, T_FN, T_TEXT, 0]:
        checked_type = t
        g = fresh(.binary)
        c = call(g, [lit(1)], NF_JUXT)
        print("{juxt_head_numeric(c)} {nodes[c].a == g} {nodes[int(nodes[c].a)].kind == .binary}")
    checked_type = T_INT
    # Shadow warnings: numbers, arrays, functions of that name, from a library.
    functions[60] = true; functions[40] = true
    head(ident(40), [lit(1)], NF_JUXT)
    local_of(60, T_ARRAY)
    head(ident(60), [lit(1)], NF_JUXT)
    local_of(60, T_FIXED)
    head(ident(60), [lit(1)], NF_JUXT)
    local_of(60, T_ND)
    head(ident(60), [lit(1)], NF_JUXT)
    local_of(60, T_TEXT)
    head(ident(60), [lit(1)], NF_JUXT)
    in_lib = call(ident(40), [lit(1)], NF_JUXT); nodes[in_lib].pos = 1 << 41
    print(juxt_head_numeric(in_lib))
    # Chains.
    marked = call(ident(40), [lit(1)], NF_JUXT)
    chained = call(marked, [lit(2)], 0)
    twice = call(chained, [lit(3)], 0)
    print("{juxt_chain_numeric(marked)} {juxt_chain_numeric(chained)} {juxt_chain_numeric(twice)} {juxt_chain_numeric(call(chained, [], 0))} {juxt_chain_numeric(lit(1))} {juxt_chain_numeric(call(ident(40), [lit(1)], 0))}")
    # Factors, products and powers.
    print(juxt_factor(call(ident(40), [lit(1)], NF_JUXT)) != 0)
    partial = call(ident(40), [lit(1)], NF_JUXT); nodes[partial].aux2 = i32(AUX2_PARTIAL)
    print(juxt_factor(partial) != 0)
    empty = call(ident(40), [], NF_JUXT)
    nodes[empty].nlist = 0
    two = call(ident(40), [ident(1), ident(2)], NF_JUXT)
    print(juxt_factor(two) != 0)
    opaque = call(ident(40), [fresh(.binary), ident(2)], NF_JUXT)
    print(juxt_factor(opaque) != 0)
    named = call(ident(40), [fresh(.namedarg)], NF_JUXT)
    print(juxt_factor(named) != 0)
    spread_arg = ident(2); nodes[spread_arg].flags = i32(NF_SPREAD)
    print(juxt_factor(call(ident(40), [spread_arg], NF_JUXT)) != 0)
    product = call(ident(40), [lit(5)], NF_JUXT)
    nodes[product].sym = 3; nodes[product].aux = 4; nodes[product].aux2 = 5; nodes[product].flags = 64
    juxt_product(product)
    print(show(product))
    power_call = call(ident(40), [lit(5)], NF_JUXT)
    power = call(ident(80), [power_call, lit(2)], 0)
    before = nodes.len()
    juxt_power(power)
    print("{show(power)} {nodes.len() - before}")
    print(show(int(nodes[power].b)))
    print("{nkids(int(nodes[power].b))} {nodes[kid(int(nodes[power].b), 0)].ival} {nodes[power_call].nlist}")
    # A value head.
    value = (args: int[], flags: int, k: NK, text: str, t: int): print(juxt_value_head(call(x, args, flags), k, text, t))
    value([lit(1)], 0, .call, "h", T_TEXT)
    value([], 0, .call, "h", T_INT)
    value([lit(1)], NF_JUXT, .call, "h", T_INT)
    value([lit(1)], 0, .ident, "h", T_INT)
    value([lit(1)], 0, .call, "h", T_INT)
    value([lit(1)], 0, .index, "h", T_INT)
    value([lit(1)], 0, .call, "(...)", T_INT)
    value([lit(1), lit(2)], 0, .index, "h", T_INT)
    value([fresh(.binary)], 0, .call, "h", T_INT)
    # String calls.
    print(juxt_string_call_hint(call(x, [fresh(.str_lit)], 0)))
    print(juxt_string_call_hint(call(x, [fresh(.str_lit)], NF_JUXT)))
    print(juxt_string_call_hint(call(x, [lit(1)], 0)))
    print(juxt_string_call_hint(call(x, [], 0)))
    print(juxt_string_call_hint(lit(1)))
    # What was written before a position, in Dewy and elsewhere, across bytes.
    source = "if  9.81 m\ta.b c  x)  y]\t z é f(g) $ 1e3 \t\t q"
    files[1].src = source
    files[0].src = source
    loop o in [0..len(source) + 3):
        print("{o} [{juxt_spaced_before(at(1, o))}]")
        print(juxt_space_hint(at(1, o)))
    print(juxt_space_hint(at(0, 4)))
    # A unit written apart.
    unit = (off: int, file: int):
        n = fresh(.ident)
        nodes[n].name = 88; nodes[n].pos = at(file, off)
        juxt_spaced_unit(n)
    unit(9, 1)
    unit(4, 1)
    unit(0, 1)
    unit(9, 0)
    in_library = fresh(.ident); nodes[in_library].pos = at(2, 9)
    files.push(SrcFile(src=source, is_dewy=true))
    juxt_spaced_unit(in_library)
    # A member after a multiplying call.
    member = (c: int):
        m = fresh(.field)
        nodes[m].a = i32(c)
        juxt_member_check(m)
    member(lit(1))
    member(call(ident(49), [lit(1)], NF_JUXT))
    member(call(ident(40), [lit(1)], NF_JUXT))
    # A group product.
    group = (a: int):
        n = fresh(.binary)
        nodes[n].a = i32(a)
        juxt_group_product(n)
        print("{nodes[n].a == a} {int(nodes[int(nodes[n].a)].flags)}")
    group(lit(1))
    group(fresh(.float_lit))
    checked = ident(40); nodes[checked].flags = i32(NF_CHECKED)
    group(checked)
    bind(90, .fns, 0)
    group(ident(90))
    group(ident(50))
    group(field(ident(44), 71))
    loop t in [T_INT, T_VAR, T_PARAM, T_FN, T_TEXT, T_ARRAY]:
        checked_type = t
        group(ident(49))
        group(fresh(.binary))
    checked_grows = false
    checked_type = T_INT
    group(ident(40))
    print("juxtapose ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_juxtapose_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare_narrow(compiler, tmp_path, release,
                            ('checker_tokens', 'source_types', 'node_store', 'checker_types', 'checker_state', 'juxtapose'), DRIVER,
                            doubles={'services.jo': SERVICES},
                            services=('ast', 'check', 'checker_expr', 'checker_call_queries', 'expr', 'lex', 'types', 'units', 'util'))
    assert output.endswith(b'juxtapose ok\n')
    for text in (b'a function or a number', b'does not multiply', b'hides the function', b'not a coefficient', b'is two expressions', b'whitespace separates', b'[9.81]'):
        assert text in output, text
