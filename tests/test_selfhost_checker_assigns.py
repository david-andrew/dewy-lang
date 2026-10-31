"""Assignments: source forms, targets, places, copies, domains, values, narrowing, fills and captures match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_loops import DRIVER as LOOPS
from tests.test_selfhost_checker_resolve import compare

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
da_tuple = (s: int) -> int:
    events.push("tuple:{s}")
    s
da_element = (s: int) -> int:
    events.push("element:{s}")
    da_outcome(2)
da_index = (s: int) -> int:
    events.push("index:{s}")
    da_outcome(3)
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
da_value = (s: int, t: int) -> int:
    events.push("value:{s}:{t}")
    last = int(nodes[s].b)
    if da_value_type != 0: return da_value_type
    int(nodes[int(nodes[s].b)].type)
da_write = (s: int, rt: int, lt: int, code: int) -> int:
    events.push("write:{s}:{rt}:{lt}:{code}")
    if code == 1: return rt
    if code == 4: return da_results.get(24) ?? -1
    da_outcome(20 + code)
da_coerce = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    n
da_compound = (s: int, t: int) -> int:
    events.push("compound:{s}:{t}")
    s
da_flow_host = (r: int, literal: int): events.push("flow:{r}:{literal}")
da_wrap = (s: int, r: int, mark: int) -> int:
    events.push("wrap:{s}:{r}:{mark}:{da_before}")
    da_before.truncate(mark)
    node(.block)
da_services = CheckerAssignHost(da_begin, da_prelude, da_tuple, da_element, da_index, da_check, da_place, da_capture, da_refine, da_value, da_write, da_coerce, da_compound, da_flow_host, da_wrap)
da_inputs = CheckerAssignInput(&nodes, &types, &structs, &files, &ctxs, &cx, &last, &da_refining, &da_narrows, &da_no_narrow, &da_current, &da_root, &da_before, &da_watch, &da_decimal_target, &da_cached, &da_fills, &T_STR, &T_MATH_INT, &da_services)
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
    print("{s}:{r}:{nodes[s].a}:{nodes[s].b}:{da_decimal_target}:{da_before}")
    print("  {events}")
    events = []
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
    run(assign(typed(.tuple, rec), typed(.call, rec)))
    run(assign(part(.index, var(rec), T_INT), typed(.int_lit, T_INT)))
    run(assign(part(.index, part(.index, var(rec), rec), T_INT), typed(.int_lit, T_INT)))
    run(assign(part(.index, var(rec), T_INT), typed(.int_lit, T_INT), 48))
    da_results[2] = 98
    run(assign(part(.field, var(rec), T_INT), typed(.int_lit, T_INT)))
    da_results[2] = 0
    da_results[3] = 97
    run(assign(part(.index, var(rec), T_INT), typed(.int_lit, T_INT)))
    da_results[3] = 0
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
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_assigns_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=STEMS).endswith(b'ok\n')


# A service's error stops the assignment where Jo's did.
@pytest.mark.parametrize('case,code', [
    ('da_fail = 1; run(assign(var(T_INT), typed(.int_lit, T_INT)))', 1),
    ('da_fail = 23; run(assign(var(T_INT), typed(.ident, T_I32)))', 23),
    ('da_fail = 13; da_watch.text_domains = 1; run(assign(var(T_STR), typed(.str_lit, T_STR)))', 13),
    ('da_fail = 14; run(assign(var(T_MATH_INT), typed(.int_lit, T_MATH_INT)))', 14),
    ('da_fail = 25; run(assign(part(.field, var(rec_type()), mk_type(.opt)), typed(.call, T_INT)))', 25),
])
def test_checker_assigns_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
rec_type = () -> int: mk_type(.struct_)
main = ():
    prepare_assigns()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=STEMS)
    assert output.rstrip().endswith(f'error:{code}'.encode())
