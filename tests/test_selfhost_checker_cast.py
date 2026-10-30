"""Casts: transmutes, literal targets, identity, conversions and the cast table match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xc_seen = 0
xc_unit = -1
xc_coercible = true
xc_bundle = false
xc_record = -1
xc_library = false
xc_replacement = 0
xc_nested = 0
xc_snapshot: Node[]
xc_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xc_nested != 0:
        inner = xc_nested; xc_nested = 0
        xc_snapshot = nodes
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); structs.push(StructInfo()); files.push(SrcFile())
        r = xc_check(inner, 0)
        events.push("nested:{r.type}:{r.bypass}")
    xc_seen = n
    if xc_replacement != 0:
        xc_seen = xc_replacement; xc_replacement = 0
    int(nodes[xc_seen].type)
xc_unit_host = (n: int) -> int:
    events.push("unit:{n}")
    xc_unit
xc_finalize_host = (n: int) -> int:
    events.push("finalize:{n}")
    int(nodes[n].type)
xc_reinterpret_host = (n: int, a: int, ft: int, tt: int) -> int:
    events.push("reinterpret:{n}:{a}:{ft}:{tt}")
    tt
xc_size_host = (t: int) -> int:
    events.push("size:{t}")
    int(types[t].size)
xc_refine_host = (n: int, t: int): events.push("refine:{n}:{t}:{int(nodes[n].kind)}")
xc_secret_host = (n: int, a: int, t: int) -> int:
    events.push("secret:{n}:{a}:{t}")
    t
xc_can_coerce_host = (n: int, from: int, to: int) -> bool:
    events.push("can:{n}:{from}:{to}")
    xc_coercible
xc_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xc_type_text_host = (n: int, t: int) -> int:
    events.push("type-text:{n}:{t}")
    T_STR
xc_set_coerce_host = (n: int, t: int):
    events.push("set:{n}:{t}")
    nodes[n].type = i32(t)
xc_bundled_host = (t: int, big: bool) -> bool:
    events.push("bundled:{t}:{big}")
    xc_bundle
xc_conversion_host = (n: int, t: int, a: int) -> int:
    events.push("conversion:{n}:{t}:{a}:{nodes[a].flags}")
    t
xc_helper_host = (n: int, a: int, decode: bool, expected: int) -> int:
    events.push("helper:{n}:{a}:{decode}:{expected}:{nodes[a].flags}")
    T_BOOL
xc_record_host = (n: int, a: int, ft: int, tt: int) -> int:
    events.push("record:{n}:{a}:{ft}:{tt}")
    xc_record
xc_text_host = (n: int, a: int, expected: int) -> int:
    events.push("text:{n}:{a}:{expected}")
    T_STR
xc_library_host = (pos: int) -> bool:
    events.push("library:{pos}")
    xc_library
xc_storage_host = (n: int): events.push("storage:{n}")
xc_error_host = (n: int, a: int, ft: int, tt: int, code: int):
    print(events)
    print("error:{n}:{a}:{ft}:{tt}:{code}")
    exit(19)
xc_services = CheckerCastHost(xc_check_host, xc_unit_host, xc_finalize_host, xc_reinterpret_host, xc_size_host, xc_refine_host, xc_secret_host, xc_can_coerce_host, xc_coerce_host, xc_type_text_host, xc_set_coerce_host, xc_bundled_host, xc_conversion_host, xc_helper_host, xc_record_host, xc_text_host, xc_library_host, xc_storage_host, xc_error_host)
xc_inputs = CheckerCastInput(&nodes, &types, &structs, &files, &xc_seen, &T_STR, &T_U8, &T_MATH_INT, &xc_services)
xc_binding = checker_cast_bind(&xc_inputs)
DEWY = 1 << 40
operand = (t: int, k: NK = .ident) -> int:
    n = node(k); nodes[n].type = i32(t); n
cast = (a: int, t: int, dewy: bool = false, bits: bool = false) -> int:
    n = node(.cast, a); nodes[n].b = i32(node(.tname, 0, t, 3))
    if dewy: nodes[n].pos = DEWY + n
    if bits: nodes[n].aux2 = 1
    n
kind = (k: TK, elem: int = 0, st: int = 0) -> int:
    types.push(TypeInfo(kind = k, elem = i32(elem), st = i32(st)))
    types.len() - 1
show = (n: int, r: CheckerCastResult):
    print("{n}:{r.type}:{r.bypass}:{int(nodes[n].kind)}:{nodes[n].a}:{nodes[n].type}:{nodes[n].flags}:{xc_seen}")
run = (n: int, expected: int = 0):
    show(n, xc_check(n, expected))
enum_of = (lit_set: int, union: bool) -> int:
    structs.push(StructInfo(lit_set = i32(lit_set), union_ = union))
    kind(.enum_, 0, structs.len() - 1)
prepare_cast = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_cast()
    bytes = int(tb_mk_array(T_U8))
    quantity = kind(.quantity)
    record = kind(.struct_)
    plain_enum = enum_of(0, false)
    set_enum = enum_of(3, false)
    union_enum = enum_of(0, true)
    # Units are a Dewy-only request; transmutes never ask.
    xc_unit = T_FLOAT
    run(cast(operand(T_INT), T_STR, true), 5)
    run(cast(operand(T_INT), T_I32, false))
    xc_unit = -1
    # Transmutes check without a hint and publish the replacement operand.
    replacement = operand(T_U64); xc_replacement = replacement
    n = cast(operand(T_INT), T_FLOAT, true, true)
    run(n)
    assert(nodes[n].a == i32(replacement))
    run(cast(operand(quantity), T_FLOAT, false, true))
    run(cast(operand(T_FLOAT), quantity, false, true))
    # Refined and secret targets belong to their owners.
    refined = kind(.refined, T_INT)
    a = operand(T_INT); xc_replacement = operand(T_I32)
    run(cast(a, refined))
    run(cast(operand(T_INT), kind(.secret, T_INT)))
    # Literal operands take the target as their hint.
    loop k in [NK.array, NK.map_lit, NK.tuple]: run(cast(operand(bytes, k), bytes))
    run(cast(operand(T_INT, .int_lit), T_FLOAT))
    run(cast(operand(T_INT, .float_lit), T_STR, true))
    xc_coercible = false
    run(cast(operand(T_INT, .int_lit), T_INT))
    # Identity after binding a variable; equality without one.
    v = int(tb_mk_var())
    run(cast(operand(v), T_INT))
    run(cast(operand(T_STR), T_STR))
    # Bytes as text needs a proof outside the library; a library cast prints them.
    xc_library = true
    run(cast(operand(bytes), T_STR, true), 7)
    xc_library = false
    run(cast(operand(kind(.typeval, T_INT)), T_STR, true))
    run(cast(operand(T_STR), set_enum, true))
    run(cast(operand(set_enum), set_enum, true))
    run(cast(operand(quantity), T_INT))
    run(cast(operand(T_FLOAT), quantity))
    fixed = int(tb_mk_fixed(T_INT, 3))
    xc_coercible = true
    run(cast(operand(int(tb_mk_array(T_INT))), fixed))
    run(cast(operand(fixed), int(tb_mk_array(T_INT))))
    # Dewy conversions: numbers, bundled records, byte helpers, `__as__`, text.
    run(cast(operand(T_INT), T_FLOAT, true))
    xc_bundle = true
    run(cast(operand(record), T_FLOAT, true))
    run(cast(operand(T_MATH_INT), record, true))
    run(cast(operand(record), T_MATH_INT, true))
    xc_bundle = false
    run(cast(operand(bytes), int(tb_mk_opt(T_STR)), true), 9)
    run(cast(operand(T_STR), bytes, true), 11)
    xc_record = T_BOOL
    run(cast(operand(record), T_INT, true))
    xc_record = -1
    run(cast(operand(record), T_STR, true), 13)
    run(cast(operand(T_BOOL), T_STR, true))
    # The cast table.
    run(cast(operand(T_INT), T_RAWPTR))
    run(cast(operand(T_NULL), T_RAWPTR))
    run(cast(operand(T_INT), T_I32))
    xc_library = true
    run(cast(operand(T_INT), T_FLOAT))
    run(cast(operand(T_STR), T_RAWPTR))
    xc_library = false
    run(cast(operand(plain_enum), T_INT))
    run(cast(operand(T_INT), plain_enum, true))
    run(cast(operand(T_BOOL), T_INT))
    run(cast(operand(T_RAWPTR), T_STR))
    # A nested cast grows every arena while the outer operand is checked.
    xc_nested = cast(operand(T_INT), T_I32)
    n = cast(operand(T_INT), T_FLOAT, true)
    run(n)
    assert(xc_snapshot.len() < nodes.len())
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_cast_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_cast',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('cast(operand(T_MATH_INT), T_INT, true, true)', 1),
    ('cast(operand(T_I32), T_FLOAT, true, true)', 2),
    ('cast(operand(T_STR), T_FLOAT, true, true)', 2),
    ('cast(operand(kind(.secret, T_INT)), T_INT)', 3),
    ('cast(operand(int(tb_mk_array(T_U8))), T_STR, true)', 4),
    ('cast(operand(int(tb_mk_fixed(T_U8, 4))), T_STR, true)', 4),
    ('cast(operand(T_INT), T_FLOAT)', 5),
    ('cast(operand(T_INT), enum_of(2, false), true)', 6),
    ('cast(operand(enum_of(2, false)), T_INT, true)', 6),
    ('cast(operand(T_STR), T_RAWPTR)', 7),
    ('cast(operand(T_STR), T_INT)', 8),
    ('cast(operand(enum_of(0, true)), T_INT)', 8),
])
def test_checker_cast_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_cast()
    xc_check({case}, 0)
    print("unreachable")
'''
    assert compare(compiler, tmp_path, False, DRIVER + main, status=19,
                   extra_stems=('checker_cast',)).rstrip().endswith(f':{code}'.encode())
