"""Intrinsic calls (len, cap, push, pop, clear, syscall, mem_copy, mem_set, panic, bytes here;
the rest the host's) match frozen Jo. check_intrinsic lives in the expression dispatcher's
leaf, so its arguments are checked by the real dispatcher (unchecked names are locals)."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_expr import DRIVER as EXPR, JO_DOUBLES, STEMS
from tests.test_selfhost_checker_resolve import compare

DRIVER = EXPR + r'''
drv_loops: ValueLoop[]
drv_refine = false
drv_grow = false
xn_rest = (n: int, id: int, args: int[], expected: int) -> int:
    events.push("rest:{n}:{id}:{args}:{expected}")
    T_STR
xn_nargs = (n: int, count: int, lo: int, hi: int, name: str):
    print("{events}")
    print("nargs:{name}:{count}:{lo}:{hi}")
    exit(19)
xn_error = (n: int, code: int, t: int):
    print("{events}")
    print("error:{n}:{t}:{code}")
    exit(19)
xn_coerce_stub = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xn_length = (n: int, a: int, t: int, expected: int) -> int:
    events.push("length:{n}:{a}:{t}:{expected}")
    T_INT
xn_resize = (a: int, operation: str, pos: int): events.push("resize:{a}:{operation}:{pos}")
xn_place = (a: int, for_mut: bool):
    events.push("place:{a}:{for_mut}")
    # (a place check may grow every arena: the leaf rereads by ID)
    if drv_grow:
        drv_grow = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); lists.push(0)
xn_mutation = (n: int, r: int) -> int:
    events.push("mutation:{n}:{r}")
    r
drv_host = CheckerIntrinsicHost(xn_rest, xn_nargs, xn_error, xn_coerce_stub, xn_length, xn_resize, xn_place, xn_mutation)
drv_input = CheckerIntrinsicInput(&nodes, &lists, &types, &structs, &files, &drv_loops, &drv_refine, &T_VOID, &T_INT, &T_STR, &T_U8, &T_RAWPTR, &T_NEVER, &drv_host)
xn_binding = checker_intrinsics_bind(&drv_input)
drv_name = 100
typed = (k: NK, t: int, flags: int = 0) -> int:
    if k == .ident and flags & 128 == 0:
        # (an unchecked name: a local of type t, bound in scope)
        drv_name += 1
        loop xe_scope.syms.len() <= drv_name: xe_scope.syms.push(0)
        xe_scope.syms[drv_name] = sym_of(.local, local_of(t, 1))
        loop xe_scope.top.len() <= drv_name: xe_scope.top.push(-1)
        xe_scope.top[drv_name] = drv_name
        named = node(.ident)
        nodes[named].name = i32(drv_name); nodes[named].flags = i32(flags)
        return named
    n = node(k)
    nodes[n].type = i32(t); nodes[n].flags = i32(flags)
    n
run = (id: int, args: int[], expected: int = 0):
    c = node(.call)
    nodes[c].a = 7
    count = events.len()
    r = check_intrinsic(c, id, args, expected)
    print("{id}:{r}:{int(nodes[c].kind)}:{nodes[c].aux}:{nodes[c].type}:{nodes[c].a}:{nodes[c].nlist}:{events.len() - count}")
'''

MAIN = r'''
main = ():
    prepare_expr()
    arr = int(tb_mk_array(T_INT))
    # len and cap: the argument checked once, then int
    run(1, [typed(.ident, arr)])
    run(27, [typed(.ident, arr, 128)])
    run(1, [typed(.ident, T_STR, 128)])
    run(1, [typed(.ident, int(tb_mk_fixed(T_INT, 3)), 128)])
    # (Dewy text's length and an soa value's are the host's calls)
    files[0].is_dewy = true
    run(1, [typed(.ident, T_STR, 128)], T_INT)
    run(27, [typed(.ident, T_STR, 128)])
    files[0].is_dewy = false
    structs.push(StructInfo(soa_ = true))
    soa = types.len()
    types.push(TypeInfo(kind = .struct_, st = i32(structs.len() - 1)))
    run(27, [typed(.ident, soa, 128)], T_INT)
    # push: a settled element of the type is not coerced; a literal is
    run(2, [typed(.ident, arr, 128), typed(.ident, T_INT, 128)])
    run(2, [typed(.ident, arr, 128), typed(.int_lit, T_INT, 256)])
    run(2, [typed(.ident, arr, 128), typed(.ident, T_I8)])
    drv_loops.push(ValueLoop(context = 1, route = 2, name = 3))
    drv_grow = true
    run(2, [typed(.ident, arr), typed(.ident, T_INT, 128)])
    run(3, [typed(.ident, arr, 128)])
    drv_loops = []
    run(6, [typed(.ident, arr, 128)])
    drv_refine = true
    run(3, [typed(.ident, arr, 128)])
    run(1, [typed(.ident, arr, 128)])
    drv_refine = false
    # syscall: literals and other int widths coerced to int, null a raw pointer
    ptr = int(tb_mk_ptr(T_INT))
    nil_arg = typed(.ident, T_NULL, 128)
    run(9, [typed(.int_lit, T_INT, 128 | 256), typed(.ident, ptr, 128), nil_arg, typed(.ident, T_I8, 128), typed(.ident, T_INT, 128), typed(.ident, T_BOOL, 128)])
    assert(nodes[nil_arg].type == i32(T_RAWPTR))
    # mem_copy, mem_set: pointers, then ints
    run(10, [typed(.ident, ptr, 128), typed(.ident, ptr), typed(.ident, T_I8, 128)])
    run(11, [typed(.ident, ptr), typed(.int_lit, T_INT, 128 | 256), typed(.ident, T_INT, 128)])
    # panic with and without a message; bytes of text
    run(14, [])
    run(14, [typed(.ident, T_STR, 128)])
    run(14, [typed(.ident, T_I8, 128)])
    run(19, [typed(.ident, T_STR)])
    # every other intrinsic is the host's, untouched
    x = typed(.ident, arr)
    run(13, [x, 5], T_INT)
    assert(nodes[x].flags == 0)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_intrinsics_twins(compiler, tmp_path, release):  # noqa: F811
    out = compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=STEMS, jo_doubles=JO_DOUBLES)
    assert out.endswith(b'ok\n') and b'length:' in out and b'rest:' in out and b'mutation:' in out


@pytest.mark.parametrize('case,expect', [
    ('run(1, [typed(.ident, T_INT, 128)])', 'error:{c}:{T_INT}:1'),
    ('run(27, [typed(.ident, int(tb_mk_fixed(T_INT, 3)), 128)])', ':1'),
    ('run(2, [typed(.ident, arr, 128), 1, 2])', ':2'),
    ('run(2, [typed(.ident, T_STR, 128), typed(.ident, T_INT, 128)])', ':3'),
    ('run(3, [typed(.ident, T_INT, 128)])', ':4'),
    ('run(6, [typed(.ident, T_STR, 128)])', ':5'),
    ('run(1, [typed(.namedarg, arr, 128)])', ':6'),
    ('run(9, [])', ':8'),
    ('run(9, [1, 2, 3, 4, 5, 6, 7, 8])', ':8'),
    ('run(9, [typed(.ident, T_STR, 128)])', ':9'),
    ('run(10, [typed(.ident, T_INT, 128), 1, 2])', ':7'),
    ('run(10, [typed(.ident, int(tb_mk_ptr(T_INT)), 128), typed(.ident, T_INT, 128), 2])', ':7'),
    ('run(10, [1, 2])', 'nargs:mem_copy:2:3:3'),
    ('run(11, [1])', 'nargs:mem_set:1:3:3'),
    ('run(14, [1, 2])', 'nargs:panic:2:0:1'),
    ('run(19, [])', 'nargs:bytes:0:1:1'),
    ('run(1, [])', 'nargs:len:0:1:1'),
    ('run(2, [typed(.ident, arr, 128)])', 'nargs:push:1:2:2'),
    ('run(3, [typed(.ident, arr, 128), 1])', 'nargs:pop:2:1:1'),
    ('run(6, [])', 'nargs:clear:0:1:1'),
])
def test_checker_intrinsics_errors(compiler, tmp_path, case, expect):  # noqa: F811
    main = f'''
main = ():
    prepare_expr()
    arr = int(tb_mk_array(T_INT))
    c = nodes.len()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=STEMS, jo_doubles=JO_DOUBLES)
    last = output.rstrip().split(b'\n')[-1]
    assert last.endswith(expect.split('}')[-1].encode()) and b'unreachable' not in output
