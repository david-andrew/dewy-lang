"""Assignments: source forms, targets, places, copies, domains, values, narrowing, fills and captures match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_loops import DRIVER as LOOPS
from tests.selfhost_expr_double import compare_leaf

STEMS = ('checker_loops', 'checker_assigns')
DRIVER = LOOPS + r'''
da_refining = false
da_narrows = 0
da_no_narrow = 0
da_current = 0
da_root = 0
da_before: int[]
da_watch = StatementWatch()
da_decimal_target = 0
da_cached = 0
da_fills: OptFill[]
da_results: {int: int} = {}
da_value_type = 0
da_fail = 0
da_grow_once = false
da_outcome = (code: int) -> int:
    if da_fail == code:
        print(events)
        print("error:{code}")
        exit(19)
    da_results.get(code) ?? 0
da_begin = (s: int, code: int) -> int:
    events.push("begin:{s}:{code}:{da_decimal_target}")
    if code == 2: da_decimal_target = 7
    da_outcome(100 + code)
da_prelude = (s: int) -> int:
    events.push("prelude:{s}")
    da_outcome(1)
# (3 unpacks to da_unpacked; 7 and 8 give back a block or the statement; refusals 40 + code)
da_unpacked = 0
da_tuple = (s: int, part: int, t: int, tt: int, code: int) -> int:
    events.push("tuple:{s}:{part}:{t}:{tt}:{code}")
    r = da_outcome(40 + code)
    if code == 3:
        last = int(nodes[s].b)
        return da_unpacked
    if code == 8 and r == 0: return s
    r
da_element = (s: int) -> int:
    events.push("element:{s}")
    da_outcome(2)
# (a record's forms answer da_results[3]; the others 50 + code)
da_index = (s: int, t: int, code: int) -> int:
    events.push("index:{s}:{t}:{code}")
    da_outcome(if code == 4: 3 else: 50 + code)
da_check = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}:{da_current}:{da_root}:{da_no_narrow}")
    if da_grow_once:
        da_grow_once = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); structs.push(StructInfo())
    last = n
    int(nodes[n].type)
da_place = (n: int): events.push("place:{n}")
da_capture = (s: int, n: int, dewy: bool):
    events.push("capture:{s}:{n}:{dewy}")
    if dewy: da_before.push(int(nodes[s].b))
da_refine = (s: int, t: int, code: int) -> int:
    events.push("refine:{s}:{t}:{code}")
    if code == 1: return t
    da_outcome(10 + code)
# (settle 1: converted to t but for zeroed bytes; 2: a variable's other type refused first)
da_value = (s: int, t: int, settle: int) -> int:
    events.push("value:{s}:{t}:{settle}")
    last = int(nodes[s].b)
    rt = if da_value_type != 0: da_value_type else: int(nodes[int(nodes[s].b)].type)
    if settle == 2 and rt != t: da_outcome(23)
    v = last
    if settle > 0 and (nodes[v].kind != .intrinsic or nodes[v].aux != 76): nodes[s].b = i32(da_coerce(v, t))
    rt
da_write = (s: int, rt: int, lt: int, code: int) -> int:
    events.push("write:{s}:{rt}:{lt}:{code}")
    if code == 1: return rt
    if code == 4: return da_results.get(24) ?? -1
    da_outcome(20 + code)
da_coerce = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    n
# (1 refined, 5 helper and 7 text updates give the statement back; 2 a quantity's and
# 4 an exact width's answer, 3, 6, 8 and 9 refusals and warnings: 30 + code)
da_update = (s: int, t: int, other: int, code: int) -> int:
    events.push("update:{s}:{t}:{other}:{code}:{nodes[s].b}")
    r = da_outcome(30 + code)
    if r == 0 and (code == 1 or code == 5 or code == 7): return s
    r
da_flow_host = (r: int, literal: int): events.push("flow:{r}:{literal}")
da_wrap = (s: int, r: int, mark: int) -> int:
    events.push("wrap:{s}:{r}:{mark}:{da_before}")
    da_before.truncate(mark)
    node(.block)
da_services = CheckerAssignHost(da_begin, da_prelude, da_tuple, da_element, da_index, da_place, da_capture, da_refine, da_value, da_write, da_coerce, da_update, da_flow_host, da_wrap)
da_inputs = CheckerAssignInput(&nodes, &lists, &types, &structs, &files, &ctxs, &cx, &last, &da_refining, &da_narrows, &da_no_narrow, &da_current, &da_root, &da_before, &da_watch, &da_decimal_target, &da_cached, &da_fills, &T_STR, &T_MATH_INT, &T_INT, &T_U64, &da_services)
da_bound = checker_assigns_bind(&da_inputs)
DEWY = 1 << 40
# target op= value (Tok.assign 47, pluseq 48)
assign = (target: int, value: int, op: int = 47, dewy: bool = true) -> int:
    s = node(.assign, target)
    nodes[s].b = i32(value)
    nodes[s].op = i32(op)
    if dewy: nodes[s].pos = DEWY + s
    s
var = (t: int, aux: int = 1, sym: int = 5) -> int:
    n = typed(.ident, t); nodes[n].aux = i32(aux); nodes[n].sym = i32(sym); n
part = (k: NK, base: int, t: int) -> int:
    n = typed(k, t, base); n
mk_type = (k: TK) -> int:
    types.push(TypeInfo(kind = k)); types.len() - 1
run = (s: int):
    r = va_assign(s)
    print("{s}:{r}:{nodes[s].a}:{nodes[s].b}:{nodes[s].aux}:{da_decimal_target}:{da_before}")
    print("  {events}")
    events = []
tuple_of = (parts: int[]) -> int:
    n = node(.tuple)
    node_set_list(mut nodes, mut lists, n, parts)
    n
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
prepare_assigns = ():
    prepare_loops()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_assigns()
    rec = mk_type(.struct_)
    structs.push(StructInfo(name = "Shape", union_ = true))
    types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1))); shape = types.len() - 1
    opt = mk_type(.opt)
    # Plain stores to locals and globals: same and other types, zeroed releases.
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    run(assign(var(T_INT), typed(.ident, T_I32)))
    run(assign(var(T_INT, 2), typed(.ident, T_I32)))
    run(assign(var(T_INT, 3), typed(.ident, T_I32)))
    zero = typed(.intrinsic, T_INT); nodes[zero].aux = 76
    run(assign(var(T_INT), zero))
    da_grow_once = true
    run(assign(var(T_STR), typed(.str_lit, T_STR), 47, false))
    # Fields and elements: written copies, captured selectors, narrowed paths.
    run(assign(part(.field, var(rec, 1, 8), T_INT), typed(.int_lit, T_INT)))
    run(assign(part(.field, var(rec, 1, 8), T_INT), typed(.int_lit, T_INT)))
    run(assign(part(.index, part(.field, var(rec, 2, 9), rec), T_INT), typed(.int_lit, T_INT)))
    run(assign(part(.index, var(rec, 1, 10), T_INT), typed(.int_lit, T_INT), 47, false))
    run(assign(part(.field, var(rec, 1, 11), shape), typed(.call, rec)))
    run(assign(part(.field, var(rec, 1, 11), opt), typed(.call, rec)))
    run(assign(var(shape, 2), typed(.call, rec)))
    da_narrows = 1
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    run(assign(part(.field, var(rec, 1, 12), T_INT), typed(.int_lit, T_INT)))
    da_narrows = 0
    # Forms passed to services: updates, tuples, custom elements, indexed targets.
    da_results[1] = 99
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    da_results[1] = 0
    # Tuples: elements checked as places, domains, other types, contracts, conversions.
    da_unpacked = int(tb_mk_tuple([T_INT, T_STR, T_MATH_INT]))
    run(assign(tuple_of([var(T_INT), typed(.hole, 0), var(T_MATH_INT)]), typed(.call, rec)))
    run(assign(tuple_of([var(T_INT), var(T_STR), var(T_MATH_INT)]), typed(.call, rec), 47, false))
    da_watch.text_domains = 1
    run(assign(tuple_of([var(T_INT), var(T_STR), var(T_I32)]), typed(.call, rec)))
    da_watch.text_domains = 0
    da_refining = true
    run(assign(tuple_of([var(T_INT), var(T_STR), typed(.hole, 0)]), typed(.call, rec)))
    da_results[47] = 95
    run(assign(tuple_of([var(T_INT), var(T_STR), typed(.hole, 0)]), typed(.call, rec)))
    da_results[47] = 0
    da_refining = false
    converted = tuple_of([var(T_INT), var(T_STR), var(T_MATH_INT)])
    run(assign(converted, typed(.call, rec)))
    nodes[kid(converted, 0)].type = i32(T_I32)
    da_results[48] = 94
    run(assign(converted, typed(.call, rec)))
    da_results[48] = 0
    run(assign(part(.index, var(rec), T_INT), typed(.int_lit, T_INT)))
    run(assign(part(.index, part(.index, var(rec), rec), T_INT), typed(.int_lit, T_INT)))
    run(assign(part(.index, var(rec), T_INT), typed(.int_lit, T_INT), 48))
    da_results[2] = 98
    run(assign(part(.field, var(rec), T_INT), typed(.int_lit, T_INT)))
    da_results[2] = 0
    da_results[3] = 97
    run(assign(part(.index, var(rec), T_INT), typed(.int_lit, T_INT)))
    da_results[3] = 0
    # Indexed targets by receiver: Dewy ranges, slices, stepped ranges, picks, records.
    array = mk_type(.array)
    sliced = part(.index, var(array), T_INT); nodes[sliced].b = i32(typed(.range, 0))
    run(assign(sliced, typed(.ident, array)))
    da_results[52] = 93
    sliced = part(.index, var(array), T_INT); nodes[sliced].b = i32(typed(.range, 0))
    run(assign(sliced, typed(.ident, array)))
    da_results[52] = 0
    stepped = part(.index, var(T_INT), T_INT); nodes[stepped].b = i32(typed(.range, 0)); nodes[int(nodes[stepped].b)].flags = i32(32768)
    run(assign(stepped, typed(.int_lit, T_INT)))
    picked = part(.index, var(array), T_INT); nodes[picked].b = i32(typed(.ident, array))
    run(assign(picked, typed(.ident, array), 47, false))
    da_results[55] = 92
    picked = part(.index, var(array), T_INT); nodes[picked].b = i32(typed(.ident, array))
    run(assign(picked, typed(.ident, array), 47, false))
    da_results[55] = 0
    literal = part(.index, var(array), T_INT); nodes[literal].b = i32(typed(.int_lit, T_INT))
    run(assign(literal, typed(.int_lit, T_INT)))
    fixed = mk_type(.fixed)
    nd = part(.index, var(fixed), T_INT)
    node_set_list(mut nodes, mut lists, nd, [typed(.int_lit, T_INT), typed(.range, 0)])
    nodes[nd].pos = DEWY + nd
    run(assign(nd, typed(.int_lit, T_INT)))
    nodes[nd].pos = 0
    run(assign(nd, typed(.int_lit, T_INT), 47, false))
    typeval = mk_type(.typeval)
    named = part(.index, var(typeval), T_INT); nodes[named].pos = DEWY + named
    run(assign(named, typed(.int_lit, T_INT)))
    # Refinements, domains, temperatures, decimals, fills.
    da_refining = true
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    da_results[12] = 96
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    da_results[12] = 0
    da_refining = false
    run(assign(var(T_STR), typed(.str_lit, T_STR)))
    da_watch.text_domains = 1
    run(assign(var(T_STR), typed(.str_lit, T_STR)))
    run(assign(var(T_MATH_INT), typed(.int_lit, T_MATH_INT)))
    run(assign(var(T_MATH_INT), typed(.int_lit, T_MATH_INT), 47, false))
    da_watch.temperature_writes = 1
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    da_decimal_target = 4
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    da_watch.decimals = 1
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    da_results[22] = 1
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    da_results[22] = 0
    da_watch.decimals = 0
    da_fills.push(OptFill(subject = 3))
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    da_results[24] = 2
    run(assign(var(T_INT), typed(.int_lit, T_INT)))
    da_fills = []
    # Growth in loops, followed siblings, compound updates.
    ctxs[cx].loop_depth = 1
    run(assign(var(T_INT), typed(.int_lit, T_INT), 48))
    da_watch.growth = 1
    run(assign(var(T_INT), typed(.int_lit, T_INT), 48))
    ctxs[cx].loop_depth = 0
    da_watch.sibling_flow = 1
    da_results[103] = rec
    run(assign(var(shape), typed(.call, rec)))
    da_watch.sibling_flow = 0
    run(assign(var(T_INT), typed(.int_lit, T_INT), 48))
    # Compound updates: refined and quantity targets, text, arrays, pointers, helper
    # calls (Dewy integers, exact widths, selections, elements, logic), numbers, shifts.
    refined = mk_type(.refined)
    run(assign(var(refined), typed(.int_lit, T_INT), 48))
    quantity = mk_type(.quantity)
    run(assign(var(quantity), typed(.int_lit, T_INT), 48))
    da_results[32] = 1
    run(assign(var(quantity), typed(.int_lit, T_INT), 48))
    da_results[32] = 0
    run(assign(var(T_STR), typed(.str_lit, T_STR), 48, false))
    run(assign(var(T_STR), typed(.str_lit, T_STR), 48))
    run(assign(var(T_STR), typed(.str_lit, T_STR), 49))
    array = mk_type(.array)
    run(assign(var(array), typed(.ident, array), 48))
    run(assign(var(array), typed(.ident, array), 48, false))
    fixed = mk_type(.fixed)
    run(assign(var(fixed), typed(.ident, fixed), 50))
    pointer = mk_type(.ptr)
    run(assign(var(pointer), typed(.ident, T_I32), 48))
    s = assign(var(pointer), typed(.ident, T_I32), 48); nodes[s].sval = 3
    run(s)
    run(assign(var(T_MATH_INT), typed(.int_lit, T_MATH_INT), 48))
    run(assign(var(T_INT), typed(.int_lit, T_INT), 49))
    run(assign(var(T_U64), typed(.int_lit, T_INT), 49, false))
    run(assign(var(T_I32), typed(.int_lit, T_INT), 49, false))
    da_results[34] = 1
    run(assign(var(T_I32), typed(.int_lit, T_INT), 49, false))
    da_results[34] = 0
    s = assign(var(T_INT), typed(.int_lit, T_INT), 48, false); nodes[s].flags = i32(16384)
    run(s)
    run(assign(part(.field, var(rec), T_INT), typed(.int_lit, T_INT), 48, false))
    run(assign(var(T_FLOAT), typed(.int_lit, T_INT), 51, false))
    run(assign(var(T_BOOL), typed(.ident, T_BOOL), 54, false))
    s = assign(var(T_BOOL), typed(.ident, T_BOOL), 54, false); nodes[s].aux2 = 1
    run(s)
    run(assign(var(rec), typed(.ident, rec), 48, false))
    run(assign(var(T_INT), typed(.str_lit, T_STR), 48, false))
    quoted = typed(.str_lit, T_STR); nodes[quoted].aux = 1
    run(assign(var(T_INT), quoted, 48, false))
    run(assign(var(T_INT), typed(.ident, T_INT), 56, false))
    literal = typed(.int_lit, T_I32); nodes[literal].flags = i32(256)
    run(assign(var(T_INT), literal, 57, false))
    run(assign(var(T_FLOAT), typed(.ident, T_FLOAT), 48, false))
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_assigns_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare_leaf(compiler, tmp_path, release, DRIVER + MAIN, 'da_check', extra_stems=STEMS).endswith(b'ok\n')


# A service's error stops the assignment where Jo's did.
@pytest.mark.parametrize('case,code', [
    ('da_fail = 1; run(assign(var(T_INT), typed(.int_lit, T_INT)))', 1),
    ('da_fail = 23; run(assign(var(T_INT), typed(.ident, T_I32)))', 23),
    ('da_fail = 23; da_watch.temperature_writes = 1; run(assign(var(T_INT), typed(.ident, T_I32)))', 23),
    ('da_fail = 13; da_watch.text_domains = 1; run(assign(var(T_STR), typed(.str_lit, T_STR)))', 13),
    ('da_fail = 14; run(assign(var(T_MATH_INT), typed(.int_lit, T_MATH_INT)))', 14),
    ('da_fail = 25; run(assign(part(.field, var(rec_type()), mk_type(.opt)), typed(.call, T_INT)))', 25),
    ('da_fail = 37; run(assign(var(T_STR), typed(.str_lit, T_STR), 48))', 37),
    ('da_fail = 53; s = part(.index, var(T_INT), T_INT); nodes[s].b = i32(typed(.range, 0)); nodes[int(nodes[s].b)].flags = i32(32768); run(assign(s, typed(.int_lit, T_INT)))', 53),
    ('da_fail = 51; s = part(.index, var(mk_type(.typeval)), T_INT); nodes[s].pos = DEWY + s; run(assign(s, typed(.int_lit, T_INT)))', 51),
    ('da_fail = 41; run(assign(tuple_of([var(T_INT)]), typed(.call, T_INT), 48))', 41),
    ('da_fail = 43; da_unpacked = int(tb_mk_tuple([T_INT])); run(assign(tuple_of([var(T_INT)]), typed(.call, T_INT)))', 43),
    ('da_fail = 45; da_unpacked = int(tb_mk_tuple([T_INT])); run(assign(tuple_of([var(T_INT)]), typed(.call, T_INT)))', 45),
    ('da_fail = 44; run(assign(tuple_of([var(T_INT)]), typed(.call, T_INT), 47, false))', 44),
    ('da_fail = 46; da_unpacked = int(tb_mk_tuple([T_STR])); run(assign(tuple_of([var(T_INT)]), typed(.call, T_INT), 47, false))', 46),
    ('da_fail = 33; run(assign(var(mk_type(.array)), typed(.ident, T_INT), 48))', 33),
    ('da_fail = 38; run(assign(var(T_INT), typed(.ident, T_FLOAT), 56, false))', 38),
    ('da_fail = 39; run(assign(var(T_INT), typed(.ident, T_FLOAT), 48, false))', 39),
    ('da_fail = 35; run(assign(part(.index, var(T_INT), T_INT), typed(.ident, T_FLOAT), 48, false))', 35),
])
def test_checker_assigns_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
rec_type = () -> int: mk_type(.struct_)
main = ():
    prepare_assigns()
    {case}
    print("unreachable")
'''
    output = compare_leaf(compiler, tmp_path, False, DRIVER + main, 'da_check', status=19, extra_stems=STEMS)
    assert output.rstrip().endswith(f'error:{code}'.encode())
