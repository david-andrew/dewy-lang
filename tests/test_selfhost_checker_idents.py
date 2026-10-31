"""Names read as values: locals, captures, globals, constants and the rest match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_literals import DRIVER as LITERALS
from tests.test_selfhost_checker_resolve import compare

DRIVER = LITERALS.split('main = ():')[0] + r'''
locals: Local[] = [Local()]
globals: Global[] = [Global()]
fns: FnInst[] = [FnInst()]
ctxs: FnCtx[]
cx = 0
xj_callee_at = 0
xj_assign_at = 0
xj_ide_on = false
xj_reads: bool[]
xj_paths = 0
xj_no_narrow = 0
xj_tests = false
xj_narrowed_to = 0
xj_grow = false
xj_ide_host = (n: int, s: int): events.push("ide:{n}:{s}")
xj_narrowed_host = (l: int) -> int:
    events.push("narrowed:{l}")
    if xj_grow:
        xj_grow = false
        loop i in [0..256): nodes.push(Node()); locals.push(Local()); globals.push(Global()); types.push(TypeInfo())
    if int(locals[l].flags) & 2048 != 0: return l + 1
    xj_narrowed_to
xj_capture_host = (l: int, narrowed: bool, pos: int) -> int:
    events.push("capture:{l}:{narrowed}")
    locals.push(Local(type = locals[l].type))
    locals.len() - 1
xj_view_host = (l: int, pos: int): events.push("view:{l}")
xj_ensure_host = (g: int, pos: int):
    events.push("ensure:{g}")
    globals[g].state = 2
xj_quantity_host = (n: int, g: int, expected: int) -> int:
    events.push("quantity:{n}:{g}:{expected}")
    T_FLOAT
xj_early_host = (n: int, g: int): events.push("early:{n}:{g}")
xj_decimal_host = (g: int): events.push("decimal:{g}")
xj_path_host = (n: int, t: int) -> int:
    events.push("path:{n}:{t}")
    T_U8
xj_constant_host = (n: int, g: int, expected: int) -> int:
    events.push("constant:{n}:{g}:{expected}")
    T_I8
xj_function_host = (n: int, expected: int, callee: bool) -> int:
    events.push("function:{n}:{expected}:{callee}")
    T_I16
xj_type_value_host = (n: int, kind: int, s: int) -> int:
    events.push("type-value:{n}:{kind}:{s}")
    int(tb_mk_typeval(T_INT))
xj_bare_host = (n: int, t: int, local: bool, callee: bool, expected: int) -> int:
    events.push("bare:{n}:{t}:{local}:{callee}")
    if local: return T_U16
    -1
xj_type_use_host = (n: int, t: int, callee: bool, expected: int) -> int:
    events.push("type-use:{n}:{t}:{callee}")
    -1
xj_error_host = (n: int, kind: int):
    print(events)
    print("error:{n}:{kind}")
    exit(19)
xj_services = CheckerIdentHost(xj_ide_host, xj_narrowed_host, xj_capture_host, xj_view_host, xj_ensure_host, xj_quantity_host, xj_early_host, xj_decimal_host, xj_path_host, xj_constant_host, xj_function_host, xj_type_value_host, xj_bare_host, xj_type_use_host, xj_error_host)
xj_inputs = CheckerIdentInput(&nodes, &types, &locals, &globals, &fns, &ctxs, &cx, &xj_callee_at, &xj_assign_at, &xj_ide_on, &xj_reads, &xj_paths, &xj_no_narrow, &xj_tests, &xj_services)
xj_binding = checker_idents_bind(&xj_inputs)
local_of = (t: int, owner: int, flags: int = 0) -> int:
    locals.push(Local(type = i32(t), owner = i32(owner), flags = i32(flags)))
    locals.len() - 1
name_node = () -> int:
    n = node(.ident); nodes[n].name = 2; n
run = (kind: int, ref: int, flags: int = 0, expected: int = 0):
    n = name_node()
    r = xj_ident(n, expected, kind, ref, 77, flags)
    print("{n}:{r.type}:{r.bypass}:{nodes[n].aux}:{nodes[n].sym}:{nodes[n].type}:{int(nodes[n].flags)}")
prepare_idents = ():
    prepare()
    refine = false
    fns.push(FnInst(kind = 0))
    fns.push(FnInst(kind = 4))
    ctxs.push(FnCtx(inst = 1, parent = -1, mod = 0))
    ctxs.push(FnCtx(inst = 1, parent = 0, mod = 0))
    ctxs.push(FnCtx(inst = 2, parent = -1, mod = 3))
    cx = 1
'''

MAIN = r'''
main = ():
    prepare_idents()
    fn_t = int(tb_mk_fn([T_INT], T_INT, 0, 0, 0, false))
    # Locals: owned, captured, narrowed after assignment, aliases, views, writes.
    own = local_of(T_INT, 1)
    run(1, own)
    print(locals[own].flags)
    outer = local_of(T_STR, 9)
    xj_grow = true
    run(1, outer)
    xj_narrowed_to = own
    run(1, local_of(T_BOOL, 9))
    xj_narrowed_to = 0
    reassigned = local_of(T_INT, 1, 2048); local_of(T_FLOAT, 1)
    run(1, reassigned)
    alias = local_of(T_INT, 1, 8)
    xj_narrowed_to = own
    run(1, alias, 1)
    xj_narrowed_to = 0
    target = local_of(T_INT, 1)
    n = name_node(); xj_assign_at = n
    r = xj_ident(n, 0, 1, target, 77, 0)
    print("{r.type}:{locals[target].flags}")
    run(1, local_of(fn_t, 1))
    # Globals: initialized on demand, read marks, top-level order, decimals, paths.
    globals.push(Global(type = i32(T_INT), mod = 0, state = 0))
    g = globals.len() - 1
    run(2, g, 2)
    print("{globals[g].fn_accessed}:{xj_reads}")
    cx = 2
    globals.push(Global(type = i32(T_STR), mod = 3, state = 2, decl = i32(node(.vardecl))))
    late = globals.len() - 1
    nodes[int(globals[late].decl)].pos = 99999
    run(2, late)
    print(globals[late].fn_accessed)
    xj_tests = true
    run(2, late)
    xj_tests = false
    cx = 1
    xj_paths = 1
    run(2, g)
    xj_paths = 0
    globals.push(Global(type = i32(int(types.len())), state = 2, is_const = true)); types.push(TypeInfo(kind = .quantity))
    run(2, globals.len() - 1)
    globals.push(Global(type = i32(fn_t), state = 2))
    run(2, globals.len() - 1)
    # Constants, functions, types and modules go to their owners.
    run(6, g, 0, T_INT)
    xj_callee_at = 9999
    run(3, 0)
    loop k in [4, 5, 7, 8, 10]: run(k, 0)
    xj_ide_on = true
    run(1, own)
    run(3, 0)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_idents_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_exact', 'checker_literals', 'checker_idents')).endswith(b'ok\n')


@pytest.mark.parametrize('kind', [0, 9, 11])
def test_checker_idents_errors(compiler, tmp_path, kind):  # noqa: F811
    main = f'''
main = ():
    prepare_idents()
    run({kind}, 0)
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_exact', 'checker_literals', 'checker_idents'))
    assert output.rstrip().endswith(f':{kind}'.encode())
