"""Tuple and dictionary literals: hints, key/value typing and float keys match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xk_floaty = false
xk_coercible = true
xk_nested = 0
xk_snapshot: Node[]
xk_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xk_nested != 0:
        inner = xk_nested; xk_nested = 0
        xk_snapshot = nodes
        loop i in [0..256): nodes.push(Node()); lists.push(0); types.push(TypeInfo()); structs.push(StructInfo()); args.push(0); files.push(SrcFile())
        r = xk_check(inner, 0, 0)
        events.push("nested:{r.type}:{r.bypass}")
    int(nodes[n].type)
xk_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xk_finalize_host = (n: int) -> int:
    events.push("finalize:{n}")
    int(nodes[n].type)
xk_values_host = (n: int, ex: int) -> int:
    events.push("values:{n}:{ex}")
    T_STR
xk_float_key_host = (t: int) -> bool:
    events.push("float-key:{t}")
    xk_floaty
xk_obligation_host = (n: int): events.push("obligation:{n}")
xk_key_name_host = (n: int): events.push("key-name:{n}")
xk_map_decl_host = (n: int) -> int:
    events.push("map:{n}")
    500
xk_instance_host = (d: int, kt: int, vt: int) -> int:
    events.push("instance:{d}:{kt}:{vt}")
    int(tb_mk_tuple([kt, vt]))
xk_setter_host = (n: int, t: int, kt: int, vt: int) -> int:
    events.push("setter:{n}:{t}:{kt}:{vt}")
    77
xk_can_coerce_host = (n: int, from: int, to: int) -> bool:
    events.push("can:{n}:{from}:{to}")
    xk_coercible
xk_error_host = (n: int, code: int, first: int, second: int):
    print(events)
    print("error:{n}:{code}:{first}:{second}")
    exit(19)
xk_services = CheckerCollectionHost(xk_check_host, xk_coerce_host, xk_finalize_host, xk_values_host, xk_float_key_host, xk_obligation_host, xk_key_name_host, xk_map_decl_host, xk_instance_host, xk_setter_host, xk_can_coerce_host, xk_error_host)
xk_inputs = CheckerCollectionInput(&nodes, &lists, &types, &structs, &args, &files, &T_VOID, &xk_services)
xk_binding = checker_collections_bind(&xk_inputs)
DEWY = 1 << 40
operand = (t: int, k: NK = .int_lit) -> int:
    n = node(k); nodes[n].type = i32(t); n
pair = (key: int, value: int) -> int:
    p = node(.pair, key); nodes[p].b = i32(value); p
show = (n: int, r: CheckerCollectionResult):
    print("{n}:{r.type}:{r.bypass}:{nodes[n].sym}:{types[r.type].kind == .tuple}")
run = (n: int, ex: int = 0):
    show(n, xk_check(n, ex, ex))
map_type = (decl: int, kt: int, vt: int) -> int:
    at = args.len(); args.push(i32(kt)); args.push(i32(vt))
    structs.push(StructInfo(decl = i32(decl), targs = i32(at), ntargs = 2))
    types.push(TypeInfo(kind = .struct_, st = i32(structs.len() - 1)))
    types.len() - 1
prepare_collections = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_collections()
    # Tuples: grouped values, the unit tuple, positional hints only at equal arity.
    grouped = node(.tuple, 0, 0, 7, [operand(T_INT)])
    run(grouped, T_FLOAT)
    run(node(.tuple), T_INT)
    pair_type = int(tb_mk_tuple([T_FLOAT, T_STR]))
    run(node(.tuple, 0, 0, 0, [operand(T_INT), operand(T_STR)]), pair_type)
    run(node(.tuple, 0, 0, 0, [operand(T_INT), operand(T_STR), operand(T_BOOL)]), pair_type)
    run(node(.tuple, 0, 0, 0, [operand(T_INT), operand(T_STR)]), T_INT)
    comprehension = node(.tuple, 0, 0, 0, [operand(T_FLOAT), operand(T_STR)]); nodes[comprehension].flags = i32(33554432)
    run(comprehension)
    xk_floaty = true
    run(comprehension)
    xk_floaty = false
    # Dictionaries: names as keys, expected dictionary types, inference from the first entry.
    key = operand(T_STR, .ident)
    entries = [pair(key, operand(T_INT)), pair(operand(T_STR), operand(T_INT))]
    run(node(.map_lit, 0, 0, 0, entries), map_type(500, T_STR, T_FLOAT))
    run(node(.map_lit, 0, 0, 0, entries), map_type(501, T_STR, T_FLOAT))
    run(node(.map_lit, 0, 0, 0, entries))
    run(node(.map_lit), map_type(500, T_INT, T_INT))
    mixed = [pair(operand(T_STR), operand(T_INT)), pair(operand(T_STR), operand(T_FLOAT))]
    run(node(.map_lit, 0, 0, 0, mixed))
    run(node(.map_lit, 0, 0, 0, mixed), map_type(500, T_STR, T_FLOAT))
    # Float keys owe an obligation per key, in Dewy only.
    xk_floaty = true
    floats = node(.map_lit, 0, 0, 0, [pair(operand(T_FLOAT), operand(T_INT)), pair(operand(T_FLOAT), operand(T_INT))])
    run(floats)
    nodes[floats].pos = DEWY + floats
    run(floats)
    xk_floaty = false
    # A nested literal grows every arena while an outer entry is checked.
    xk_nested = node(.tuple, 0, 0, 0, [operand(T_INT)])
    run(node(.map_lit, 0, 0, 0, [pair(operand(T_STR), operand(T_INT)), pair(operand(T_STR), operand(T_INT))]))
    assert(xk_snapshot.len() < nodes.len())
    xk_nested = node(.map_lit, 0, 0, 0, [pair(operand(T_STR), operand(T_INT))])
    run(node(.tuple, 0, 0, 0, [operand(T_INT), operand(T_INT)]), pair_type)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_collections_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_collections',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('node(.map_lit)', 1),
    ('node(.map_lit, 0, 0, 0, [pair(operand(T_STR), operand(T_INT)), pair(operand(T_STR), operand(T_STR))])', 2),
])
def test_checker_collections_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_collections()
    xk_coercible = false
    xk_check({case}, 0, 0)
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_collections',))
    assert output.rstrip().split(b'\n')[-1].split(b':')[2] == str(code).encode()
