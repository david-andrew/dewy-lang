"""Array and record literals: shapes, element typing, spreads and packs match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xr_seen = 0
xr_site = 0
xr_hit = 0
xr_map = false
xr_positional = 0
xr_record_made = 0
xr_parent = 0
xr_grow = false
# An element's ival: 7 makes it a pack function's call (sets the hit).
xr_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}:{xr_site}")
    if xr_grow:
        xr_grow = false
        loop i in [0..256): nodes.push(Node()); lists.push(0); types.push(TypeInfo()); files.push(SrcFile())
    if nodes[n].ival == 7: xr_hit = 1
    xr_seen = n
    int(nodes[n].type)
xr_check_to_host = (n: int, t: int) -> int:
    events.push("check-to:{n}:{t}")
    t
xr_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xr_finalize_host = (n: int) -> int:
    events.push("finalize:{n}")
    int(nodes[n].type)
xr_decimal_host = (pos: int) -> int:
    events.push("decimal:{pos}")
    T_F32
xr_spread_host = (n: int, ex: int, expected: int) -> int:
    events.push("spread:{n}:{ex}:{expected}")
    T_STR
xr_record_spread_host = (n: int, expected: int) -> int:
    events.push("record-spread:{n}:{expected}")
    T_STR
xr_reflect_host = (n: int): events.push("reflect:{n}")
xr_record_type_host = (n: int) -> int:
    events.push("record-type:{n}")
    xr_record_made
xr_map_host = (t: int) -> bool:
    events.push("map:{t}")
    xr_map
xr_positional_host = (n: int, ex: int) -> int:
    events.push("positional:{n}:{ex}")
    xr_positional
xr_construct_host = (n: int, t: int, entries: bool, expected: int) -> int:
    events.push("construct:{n}:{t}:{entries}:{expected}")
    t
xr_fixed_host = (n: int, t: int): events.push("fixed:{n}:{t}:{nodes[n].type}")
xr_values_host = (n: int, i: int, v: int, expected: int) -> int:
    events.push("values:{n}:{i}:{v}:{expected}")
    T_BOOL
xr_parent_host = (n: int) -> int:
    events.push("parent:{n}")
    xr_parent
xr_sibling_host = (n: int) -> int:
    events.push("sibling:{n}")
    T_U8
xr_coerce_all_host = (n: int, elt: int, spread: bool):
    events.push("coerce-all:{n}:{elt}:{spread}")
xr_error_host = (n: int, code: int, t: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
xr_services = CheckerAggregateHost(xr_check_host, xr_check_to_host, xr_coerce_host, xr_finalize_host, xr_decimal_host, xr_spread_host, xr_record_spread_host, xr_reflect_host, xr_record_type_host, xr_map_host, xr_positional_host, xr_construct_host, xr_fixed_host, xr_values_host, xr_parent_host, xr_sibling_host, xr_coerce_all_host, xr_error_host)
xr_inputs = CheckerAggregateInput(&nodes, &lists, &types, &files, &xr_seen, &xr_site, &xr_hit, &T_INT, &T_MATH_INT, &T_FLOAT, &T_STR, &T_U64, &xr_services)
xr_binding = checker_aggregates_bind(&xr_inputs)
DEWY = 1 << 40
item = (t: int, k: NK = .ident, flags: int = 0) -> int:
    n = node(k); nodes[n].type = i32(t); nodes[n].flags = i32(flags); n
lit = (k: NK, t: int) -> int: item(t, k, 256)
array = (items: int[], dewy: bool = false, repeat: int = 0) -> int:
    n = node(.array, 0, 0, 0, items); nodes[n].b = i32(repeat)
    if dewy:
        nodes[n].pos = DEWY + n
        loop c in items: nodes[c].pos = DEWY + c
    n
record_type = () -> int:
    structs.push(StructInfo(resolved = true))
    types.push(TypeInfo(kind = .struct_, st = i32(structs.len() - 1)))
    types.len() - 1
run = (n: int, ex: int = 0):
    r = xr_check(n, ex, ex)
    print("{n}:{r.type}:{r.bypass}:{int(nodes[n].kind)}:{nodes[n].aux}:{nodes[n].type}")
prepare_aggregates = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_aggregates()
    rec = record_type()
    # Records: field names reflect, spreads rewrite, expected or inferred record types.
    named = node(.namedarg, item(T_INT))
    xr_grow = true
    run(node(.record_lit, 0, 0, 0, [named, item(T_INT)]), rec)
    run(node(.record_lit, 0, 0, 0, [item(T_INT, .ident, 1024)]), rec)
    run(node(.record_lit), int(tb_mk_opt(rec)))
    xr_record_made = rec
    run(node(.record_lit))
    run(node(.record_lit), int(tb_mk_var()))
    # Arrays as records, fixed arrays, dictionaries and tuples.
    run(array([item(T_INT), item(T_INT, .ident, 1024)]), int(tb_mk_array(T_INT)))
    run(array([], true), rec)
    run(array([], true), int(tb_mk_opt(rec)))
    xr_map = true
    run(array([], true), rec)
    xr_map = false
    xr_positional = rec
    run(array([item(T_INT), item(T_STR)], true), rec)
    xr_positional = 0
    fixed = int(tb_mk_fixed(T_INT, 3))
    run(array([item(T_INT), item(T_INT), item(T_INT)]), fixed)
    run(array([item(T_INT)], false, item(T_INT)), fixed)
    run(array([]), fixed)
    run(array([item(T_INT), item(T_INT)]), fixed)
    spreads = array([item(T_INT), item(T_INT), item(T_INT)]); nodes[spreads].aux = 2
    run(spreads, fixed)
    map_t = record_type()
    xr_map = true
    run(array([], true), map_t)
    xr_map = false
    pair = int(tb_mk_tuple([T_INT, T_STR]))
    run(array([item(T_INT), item(T_STR)], true), pair)
    run(array([item(T_INT, .ident, 1024)], true), pair)
    run(array([item(T_INT), item(T_STR)]), pair)
    # Repeated values and empty arrays.
    run(array([item(T_STR)], false, item(T_INT)), int(tb_mk_array(T_STR)))
    run(array([lit(.int_lit, T_INT)], false, item(T_INT)))
    run(array([]), int(tb_mk_array(T_BOOL)))
    run(array([]))
    # Elements: literals choose the element type; spreads bring their arrays' elements.
    run(array([lit(.int_lit, T_INT), lit(.int_lit, T_INT)]))
    run(array([lit(.int_lit, T_INT), lit(.int_lit, T_INT)], true))
    run(array([lit(.int_lit, T_INT), lit(.float_lit, T_FLOAT)]))
    decimal = lit(.float_lit, T_FLOAT); nodes[decimal].sval = 3
    run(array([lit(.int_lit, T_INT), decimal]))
    char = item(T_STR, .str_lit, 256 | 512)
    run(array([char, item(T_STR, .str_lit, 256 | 512)]))
    run(array([char, item(T_STR)]))
    enum_t = int(types.len()); types.push(TypeInfo(kind = .enum_))
    run(array([lit(.ident, enum_t), item(T_INT)]))
    run(array([item(int(tb_mk_array(T_STR)), .ident, 1024), item(T_STR)]))
    run(array([item(T_STR), item(int(tb_mk_array(T_STR)), .ident, 1024)]))
    run(array([item(T_INT), item(T_INT)]), int(tb_mk_array(T_INT)))
    run(array([item(T_INT), item(T_INT)]), int(tb_mk_array(int(tb_mk_var()))))
    run(array([lit(.unary, T_INT)]))
    # Multi-value packs: a pack spreads its values or is collected again.
    values = int(tb_mk_values([T_INT, T_INT]))
    p = item(values); nodes[p].ival = 7
    run(array([item(T_INT), p]))
    p = item(values, .ident, 1024); nodes[p].ival = 7
    run(array([p]))
    p = item(int(tb_mk_array(T_INT))); nodes[p].ival = 7
    run(array([p, lit(.int_lit, T_INT)]))
    p = item(int(tb_mk_array(T_INT))); nodes[p].ival = 7
    run(array([p]), int(tb_mk_array(T_INT)))
    # Families: siblings keep their positions in Dewy.
    xr_parent = 5
    run(array([item(rec), item(rec)], true))
    run(array([item(rec), item(rec, .ident, 1024)], true))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_aggregates_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_aggregates',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('n = array([]); nodes[n].flags = i32(1048576); run(n)', 1),
    ('run(array([item(T_INT)], true), int(tb_mk_tuple([T_INT, T_STR])))', 2),
    ('run(node(.record_lit))', 4),
    ('xr_map = true; run(node(.record_lit), record_type())', 4),
])
def test_checker_aggregates_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_aggregates()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_aggregates',))
    assert output.rstrip().endswith(f':{code}'.encode())
