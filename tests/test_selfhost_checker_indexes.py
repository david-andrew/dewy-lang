"""Indexing: constructors, positions, soa, parts, slices, picks and element types match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xx_part = -1
xx_range = false
xx_grow = false
xx_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xx_grow:
        xx_grow = false
        loop i in [0..256): nodes.push(Node()); lists.push(0); types.push(TypeInfo()); structs.push(StructInfo()); files.push(SrcFile())
    int(nodes[n].type)
xx_check_to_host = (n: int, t: int) -> int:
    events.push("check-to:{n}:{t}")
    t
xx_construct_host = (n: int, t: int, expected: int) -> int:
    events.push("construct:{n}:{t}:{expected}")
    T_STR
xx_position_host = (n: int, t: int, expected: int) -> int:
    events.push("position:{n}:{t}:{expected}")
    T_BOOL
xx_type_value_host = (n: int) -> int:
    events.push("type-value:{n}")
    T_U16
xx_soa_host = (n: int, expected: int) -> int:
    events.push("soa:{n}:{expected}")
    T_U32
xx_part_host = (n: int, t: int, expected: int) -> int:
    events.push("part:{n}:{t}:{expected}")
    xx_part
xx_negative_host = (n: int): events.push("negative:{n}")
xx_operator_host = (n: int, b: int, expected: int) -> int:
    events.push("operator:{n}:{b}:{expected}")
    T_I8
xx_range_host = (t: int) -> bool:
    events.push("int-range:{t}")
    xx_range
xx_select_host = (n: int, b: int, t: int, kind: int, expected: int) -> int:
    events.push("select:{n}:{b}:{t}:{kind}:{expected}")
    T_I16
xx_deref_host = (pos: int, t: int): events.push("deref:{pos}:{t}")
xx_error_host = (n: int, code: int, t: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
xx_services = CheckerIndexHost(xx_check_host, xx_check_to_host, xx_construct_host, xx_position_host, xx_type_value_host, xx_soa_host, xx_part_host, xx_negative_host, xx_operator_host, xx_range_host, xx_select_host, xx_deref_host, xx_error_host)
xx_inputs = CheckerIndexInput(&nodes, &lists, &types, &structs, &files, &T_INT, &T_MATH_INT, &T_U8, &T_RANGE, &T_MAT4, &T_VEC4, &T_I32, &T_F32, &xx_services)
xx_binding = checker_indexes_bind(&xx_inputs)
DEWY = 1 << 40
item = (t: int, k: NK = .ident) -> int:
    n = node(k); nodes[n].type = i32(t); n
index = (t: int, b: int, dewy: bool = false, extra: int[] = []) -> int:
    n = node(.index, item(t), 0, 0, extra); nodes[n].b = i32(b)
    if dewy: nodes[n].pos = DEWY + n
    n
slice = (lo: int, hi: int) -> int:
    r = node(.range, lo); nodes[r].b = i32(hi); r
record = (soa: bool) -> int:
    structs.push(StructInfo(soa_ = soa, resolved = true))
    types.push(TypeInfo(kind = .struct_, st = i32(structs.len() - 1)))
    types.len() - 1
run = (n: int, expected: int = 0):
    bt = int(nodes[int(nodes[n].a)].type)
    r = xx_index(n, expected, bt)
    print("{n}:{r.type}:{r.bypass}:{nodes[n].aux}")
prepare_indexes = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_indexes()
    tv = int(types.len()); types.push(TypeInfo(kind = .typeval, elem = i32(T_INT)))
    pair = int(tb_mk_tuple([T_INT, T_STR]))
    arr = int(tb_mk_array(T_STR))
    fixed = int(tb_mk_fixed(T_BOOL, 3))
    rec = record(false)
    soa = record(true)
    xx_grow = true
    run(index(tv, item(T_INT), true), T_INT)
    run(index(tv, item(T_INT)))
    run(index(pair, item(T_INT), true))
    run(index(soa, item(T_INT)))
    xx_part = T_FLOAT
    run(index(rec, item(T_INT)))
    xx_part = -1
    # Slices: bounds are integers; a fixed array's slice is an array.
    run(index(arr, slice(item(T_INT), item(T_INT))))
    run(index(fixed, slice(0, item(T_INT))))
    run(index(T_STR, slice(0, 0)))
    # Operators of records, with one index or several.
    run(index(rec, 0, false, [item(T_INT), item(T_INT)]))
    run(index(rec, item(T_INT)))
    # Elements: picks by range, mask or index array; negative literals; fixed bounds.
    run(index(arr, item(T_INT)))
    run(index(arr, item(T_INT, .int_lit)))
    run(index(fixed, item(T_INT, .int_lit)))
    run(index(arr, item(int(tb_mk_array(T_BOOL)))), arr)
    run(index(arr, item(int(tb_mk_array(T_INT)))))
    run(index(fixed, item(int(tb_mk_array(T_MATH_INT)))))
    empty = item(int(tb_mk_array(T_INT)), .array)
    run(index(arr, empty))
    range_t = record(false)
    xx_range = true
    run(index(arr, item(range_t)))
    xx_range = false
    run(index(arr, item(range_t)))
    run(index(T_STR, item(T_INT)))
    run(index(T_STR, item(T_INT, .int_lit)))
    run(index(int(tb_mk_ptr(T_U8)), item(T_INT)))
    run(index(T_VEC3, item(T_INT)))
    run(index(T_IVEC3, item(T_INT)))
    run(index(T_MAT4, item(T_INT)))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_indexes_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_indexes',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('run(index(int(tb_mk_array(T_INT)), item(int(tb_mk_array(T_STR)))))', 1),
    ('run(index(T_INT, slice(0, 0)))', 2),
    ('run(index(int(tb_mk_array(T_INT)), 0))', 3),
    ('b = item(T_INT, .int_lit); nodes[b].ival = 3; run(index(int(tb_mk_fixed(T_INT, 3)), b))', 4),
    ('b = item(T_INT, .int_lit); nodes[b].ival = -1; run(index(int(tb_mk_fixed(T_INT, 3)), b))', 4),
    ('run(index(T_BOOL, item(T_INT)))', 5),
])
def test_checker_indexes_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_indexes()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_indexes',))
    assert output.rstrip().endswith(f':{code}'.encode())
