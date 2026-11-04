"""Value queries, deferred pack expansion and sink restoration match frozen Jo."""
import re
import pytest
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import compare
from tests.test_selfhost_checker_call_convert import DRIVER as BASE, JO as BASE_JO, DOUBLES

JO = dict(BASE_JO)

def replace(module, name, definition):
    JO[module] = re.sub(r'(?m)^' + name + r' = [^\n]*(?:\n(?:    [^\n]*|[ \t]*))*', definition.rstrip() + '\n', JO[module])

replace('ast.jo', 'set_list', 'set_list = (n: int, xs: int[]): decl_children[n] = xs; nodes[n].nlist = i32(xs.len())')
JO['ast.jo'] += r'''
const NF_INBOUNDS = 524288
const NF_INDEX_CAPTURED = 268435456
const NF_WRITTEN_VOID = NF_INDEX_CAPTURED
const TUPLE_VALUES = 7
mk = (k: NK, pos: int) -> int: n = nodes.len(); nodes.push(Node(kind=k, pos=pos)); n
'''
replace('ast.jo', 'clone', r'''clone = (a: int) -> int:
    va_snapshot = nodes
    loop i in [0..128): nodes.push(Node())
    n = nodes.len(); nodes.push(nodes[a]); n
''')
JO['expr.jo'] += r'''
last_checked = 0
mk_ident_local = (l: int, pos: int) -> int:
    if va_ident_growth:
        va_ident_growth = false
        va_snapshot = nodes
        loop i in [0..128): nodes.push(Node())
    n = mk(.ident, pos); nodes[n].sym = i32(l); nodes[n].aux = i32(int(SK.local)); n
bc_stmt = (v: int, pos: int) -> int:
    n = mk(.exprstmt, pos); nodes[n].a = i32(v); n
bc_block = (xs: int[], pos: int) -> int:
    n = mk(.block, pos); set_list(n, xs); n
call_collect_named = (name: int, mod: int, ds: mut int[]):
    events.push("collect:{name}")
    loop d in candidates: ds.push(d)
'''
replace('expr.jo', 'capture_value', r'''capture_value = (a: int, pt: int, ss: mut int[]) -> int:
    events.push("capture:{a}"); ss.push(a)
    if va_grow:
        va_grow = false
        va_snapshot = nodes
        loop i in [0..128): nodes.push(Node()); types.push(TypeInfo()); locals.push(Local())
    n = mk_ident_local(7, nodes[a].pos)
    n
''')
JO['check.jo'] += r'''
sink_pack_site = 0
sink_pack_hit = 0
sink_bind_next = 0
sink_bind_expect = 0
spread_calls: bool[]
node_marked = (xs: bool[], n: int) -> bool: n < xs.len() and xs[n]
dewy_at = (pos: int) -> bool: va_dewy
ensure_global = (g: int, pos: int): events.push("global:{g}"); globals[g].type = i32(va_global_type)
check_fn_body = (f: int):
    events.push("body:{f}")
    if va_error: print("body-error"); exit(42)
    fns[f].pack = va_pack
values_init_error = (k: int, v: int, expected: int, t: int): print("values-error:{k}:{sink_pack_site}"); exit(41)
'''
replace('services.jo', 'cr_check', r'''cr_check = (a: int, pt: int) -> int:
    events.push("check:{a}:{pt}:{sink_pack_site}:{sink_bind_next}:{sink_bind_expect}")
    last_checked = a
    if va_hit and sink_pack_site == a: sink_pack_hit = a
    if nodes[a].type == 0: nodes[a].type = i32(T_INT)
    int(nodes[a].type)
''')
JO['types.jo'] += r'''
is_values = (t: int) -> bool: t > 0 and types[prune(t)].kind == .tuple and types[prune(t)].sign
fn_type_pack = (t: int) -> bool: t > 0 and types[t].kind == .fn_ and types[t].sign
mk_values = (ts: int[]) -> int: int(tb_mk_values(ts))
'''
# Override resolver defaults: candidate tests choose a declared pack explicitly.
JO['check.jo'] += 'pack_result_count = (n: int) -> int: if n == 0: 0 else: int(nodes[n].ival)\n'
JO['types.jo'] += r'''get_struct_inst = (d: int, ts: int[]) -> int:
    va_type_snapshot = types
    loop i in [0..128): types.push(TypeInfo())
    va_struct_type = cv_type(.struct_)
    types[va_struct_type].st = 7
    va_struct_type
'''

DRIVER = BASE + r'''
va_grow = false
va_ident_growth = false
va_snapshot: Node[]
va_dewy = true
va_hit = false
va_error = false
va_pack = 1
va_global_type = 0
va_struct_type = 0
va_type_snapshot: TypeInfo[]
candidates: int[]
va_node = (k: NK, t: int = 0, xs: int[] = []) -> int:
    n = cr_arg(k, t); set_list(n, xs); n
va_sym = (k: SK, ref: int, t: int = 0) -> int:
    s = syms.len(); syms.push(Sym(kind=k, ref=i32(ref)))
    n = va_node(.ident, t); nodes[n].name = i32(s); n
va_call = (k: int) -> int:
    f = fns.len(); fns.push(FnInst(pack_k=k))
    n = va_node(.call, int(tb_mk_array(T_INT))); nodes[n].sym = i32(f); n
va_local = (t: int) -> int:
    l = locals.len(); locals.push(Local(type=i32(t)))
    n = va_sym(.local, l, t); nodes[n].sym = i32(l); nodes[n].aux = i32(int(SK.local)); n
'''
MAIN = r'''main = ():
    prepare(); events = []
    pair = mk_values([T_INT, T_INT]); triple = mk_values([T_INT, T_INT, T_INT])
    a = va_node(.int_lit, T_INT); b = va_node(.bool_lit, T_BOOL)
    group = va_node(.tuple, pair, [a, b]); nodes[group].aux = i32(TUPLE_VALUES)
    assert(values_count(group) == 2)
    pre: int[]
    assert(values_parts(group, pre) == [a, b] and pre.len() == 0)
    local = va_local(pair)
    assert(values_candidate(local))
    va_ident_growth = true
    ps = values_parts(local, pre)
    assert(not va_ident_growth)
    assert(ps.len() == 2 and pre.len() == 0 and nodes[ps[0]].kind == .field and nodes[ps[1]].ival == 1)
    call = va_call(2)
    assert(values_count(call) == 2)
    va_grow = true
    ps = values_parts(call, pre)
    assert(not va_grow and ps.len() == 2 and pre == [call])
    assert(nodes[ps[0]].kind == .index and has_flag(ps[0], NF_INBOUNDS))
    assert(nodes[int(nodes[ps[1]].b)].ival == 1)
    # Written grouping and spreading flatten only untouched syntax.
    outer = va_node(.tuple, 0, [group, a]); nodes[outer].aux = i32(TUPLE_VALUES)
    assert(values_flatten([outer]) == [a, b, a])
    spread = va_node(.array, 0, [a, b]); add_flag(spread, NF_SPREAD)
    assert(values_flatten([spread]) == [a, b])
    add_flag(a, NF_SPREAD); assert(values_flatten([spread]) == [spread]); nodes[a].flags = 0
    add_flag(group, NF_CHECKED); assert(values_flatten([group]) == [group]); nodes[group].flags = 0
    array = va_node(.array, 0, [a, group])
    assert(values_grouped(array))
    nodes[array].type = i32(T_INT); assert(not values_grouped(array)); nodes[array].type = 0
    assert(values_simple(a) and values_simple(va_node(.record_lit, 0, [a, b])))
    str = va_node(.str_lit); assert(values_simple(str)); nodes[str].aux = 1; assert(not values_simple(str))
    field = va_node(.field); nodes[field].a = i32(a); assert(values_simple(field))
    assert(not values_simple(call) and not values_simple(va_node(.array, 0, [call])))
    # Candidate queries and bare-name call rewriting.
    assert(values_candidate(va_node(.call)))
    spread_calls = fill(false, nodes.len())
    c = va_node(.call); spread_calls.push(true); assert(not values_candidate(c))
    assert(not values_candidate(va_node(.lambda)))
    add_flag(local, NF_MUT); assert(not values_candidate(local)); nodes[local].flags = 0
    g = globals.len(); globals.push(Global()); va_global_type = pair
    assert(values_candidate(va_sym(.global, g)))
    assert(not values_candidate(va_local(T_INT)))
    ft = cv_type(.fn_, pair); types[ft].sign = true
    fnlocal = va_local(ft); assert(values_candidate(fnlocal) and nodes[fnlocal].kind == .call)
    d = cr_decl([T_INT, T_INT], defaults=[a, b]); candidates = [d]
    fn = va_sym(.fns, d); call = va_node(.call); nodes[call].a = i32(fn)
    dewy_param_kinds[d] = [0, 1]
    assert(values_arity(call) == 1)
    candidates = [d, d]; assert(values_arity(call) == -1 and not values_candidate(fn)); candidates = [d]
    add_flag(d, NF_GENERIC); assert(not values_candidate(fn)); nodes[d].flags = 0
    assert(values_candidate(fn) and nodes[fn].kind == .call)
    nominal = va_sym(.struct_, d)
    assert(values_record(nominal) == 7)
    nodes[d].nlist2 = 1; assert(values_record(nominal) == 0)
    assert(values_record(a) == 0 and values_arity(va_node(.call)) == -1)
    # Sink entry and restoration, including block hints and unknown dynamic packs.
    sink_pack_site = 77; va_dewy = false
    assert(values_init(a, T_INT) == T_INT and sink_pack_site == 77)
    va_dewy = true
    block = va_node(.block, pair)
    assert(values_init(block, pair) == pair and sink_pack_site == 77 and sink_bind_next == 0 and sink_bind_expect == 0)
    dynamic = va_call(0); va_hit = true
    assert(values_init(dynamic, 0, true) == int(nodes[dynamic].type) and sink_pack_site == 77)
    fixed = va_call(2); va_grow = true
    result = values_init(fixed, 0)
    assert(is_values(result) and types[result].nargs == 2 and nodes[last_checked].kind == .block)
    assert(sink_pack_site == 77 and sink_pack_hit == 0 and not va_grow)
    # Array splice has both direct and capture-prelude paths.
    array = va_node(.array, 0, [a, group, b]); values_elements(array, 1, group, 0)
    assert(kids(array) == [a, a, b, b])
    fixed = va_call(2); array = va_node(.array, 0, [fixed]); va_grow = true
    result = values_elements(array, 0, fixed, T_INT)
    assert(result == T_INT and nodes[array].kind == .block and last_checked == array and not va_grow)
    print(events)
    loop n in nodes: print("{int(n.kind)}:{n.a}:{n.b}:{n.aux}:{n.type}:{n.sym}:{n.flags}")
    print("ok")
'''

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_values_twins(compiler, tmp_path, release):
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_values', 'checker_call_cost', 'checker_call_convert'),
                   doubles=DOUBLES, jo_doubles=JO).endswith(b'ok\n')

@pytest.mark.parametrize('case,status,message', [
    ('x = va_node(.block, mk_values([T_INT])); values_init(x, mk_values([T_INT, T_INT]))', 41, 'values-error:1'),
    ('va_hit = true; values_init(va_call(0), 0)', 41, 'values-error:2'),
    ('va_error = true; d = cr_decl([]); candidates = [d]; values_candidate(va_sym(.fns, d))', 42, 'body-error'),
])
def test_checker_values_errors(compiler, tmp_path, case, status, message):
    output = compare(compiler, tmp_path, False, DRIVER + 'main = ():\n    prepare()\n    ' + case + '\n    print("unreachable")\n',
                     status=status, extra_stems=('checker_values', 'checker_call_cost', 'checker_call_convert'),
                     doubles=DOUBLES, jo_doubles=JO)
    assert message.encode() in output
