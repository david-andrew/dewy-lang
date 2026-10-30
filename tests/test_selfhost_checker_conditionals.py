"""`if` and `if let`: branch order, narrowing lifetimes, fills and joins match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
locals: Local[] = [Local()]
xf_scope = CheckerScope()
xf_log: int[]
xf_sink_at = 0
xf_fill = 0
xf_fill_ok = false
xf_jump = 0
xf_grow = false
xf_source = 0
xf_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    int(nodes[n].type)
xf_check_to_host = (n: int, t: int) -> int:
    events.push("check-to:{n}:{t}")
    if xf_grow:
        xf_grow = false
        loop i in [0..256): nodes.push(Node()); lists.push(0); types.push(TypeInfo()); locals.push(Local()); files.push(SrcFile())
    t
xf_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xf_finalize_host = (n: int) -> int:
    events.push("finalize:{n}")
    int(nodes[n].type)
# A body's ival: 1 terminates (a lowered block's flag), 2 logs a narrowing write, 4 binds
# a name, 8 adds a local.
xf_block_host = (b: int, expected: int, value: bool, jumps: mut int) -> int:
    xf_jump += 1
    jumps = xf_jump
    events.push("block:{b}:{expected}:{value}:{xf_scope.names.len()}:{xf_log.len()}")
    bits = nodes[b].ival
    if bits & 2 != 0: xf_log.push(locals.len() - 1)
    if bits & 4 != 0: xf_scope.names.push(b)
    if bits & 8 != 0: locals.push(Local())
    int(nodes[b].type)
xf_returned_host = (changes: int, jumps: int, b: int):
    events.push("returned:{changes}:{jumps}:{b}")
    if nodes[b].ival & 1 != 0: xf_log.truncate(changes)
xf_terminates_host = (s: int) -> bool:
    events.push("terminates:{s}")
    nodes[s].ival & 1 != 0
xf_narrow_host = (c: int, holds: bool):
    events.push("narrow:{c}:{holds}")
    xf_scope.names.push(c)
    locals.push(Local())
xf_reset_host = (mark: int):
    events.push("reset:{mark}")
    xf_scope.names.truncate(mark)
xf_restored: int[][]
xf_restore_host = (changes: int):
    events.push("restore:{changes}")
    out: int[]
    loop i in [changes..xf_log.len()): out.push(xf_log[i])
    xf_log.truncate(changes)
    xf_restored.push(out)
xf_merge_host = (): events.push("merge:{xf_restored.pop()}")
xf_promote_host = (first: int, limit: int): events.push("promote:{first}:{limit}")
xf_fill_subject_host = (c: int, b: int) -> int:
    events.push("fill:{c}:{b}")
    xf_fill
xf_fill_end_host = (b: int) -> bool:
    events.push("fill-end:{b}")
    xf_fill_ok
xf_filled_host = (fill: int) -> bool:
    events.push("filled:{fill}")
    true
xf_void_member_host = (t: int) -> bool:
    events.push("void-member:{t}")
    false
xf_then_literal_host = (b: int) -> int:
    events.push("then-literal:{b}")
    n = node(.array); nodes[n].type = i32(T_STR); n
xf_sink_host = (n: int, b: int): events.push("sink:{n}:{b}")
xf_union_host = (a: int, b: int) -> int:
    events.push("union:{a}:{b}")
    int(tb_mk_tuple([a, b]))
xf_map_host = (t: int) -> bool:
    events.push("map:{t}")
    false
xf_join_host = (a: int, b: int, ex: int, pos: int) -> int:
    events.push("join:{a}:{b}:{ex}:{pos}")
    if ex != 0: return ex
    T_FLOAT
xf_source_host = (n: int) -> int:
    events.push("source:{n}")
    xf_source
xf_binding_host = (name: int, t: int, pos: int) -> int:
    events.push("binding:{name}:{t}:{pos}")
    locals.push(Local(name = i32(name), type = i32(t)))
    locals.len() - 1
xf_error_host = (n: int, t: int, code: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
xf_services = CheckerConditionalHost(xf_check_host, xf_check_to_host, xf_coerce_host, xf_finalize_host, xf_block_host, xf_returned_host, xf_terminates_host, xf_narrow_host, xf_reset_host, xf_restore_host, xf_merge_host, xf_promote_host, xf_fill_subject_host, xf_fill_end_host, xf_filled_host, xf_void_member_host, xf_then_literal_host, xf_sink_host, xf_union_host, xf_map_host, xf_join_host, xf_source_host, xf_binding_host, xf_error_host)
xf_inputs = CheckerConditionalInput(&nodes, &lists, &types, &structs, &files, &locals, &xf_scope, &xf_log, &xf_sink_at, &T_VOID, &T_BOOL, &T_NONE, &T_NEVER, &xf_services)
xf_binding = checker_conditionals_bind(&xf_inputs)
DEWY = 1 << 40
operand = (t: int, k: NK = .ident) -> int:
    n = node(k); nodes[n].type = i32(t); n
less = () -> int:
    n = node(.binary, operand(T_INT)); nodes[n].op = i32(int(Tok.lt)); nodes[n].b = i32(operand(T_INT)); n
is_none = (op: Tok) -> int:
    n = node(.binary, operand(T_INT)); nodes[n].op = i32(int(op)); nodes[n].b = i32(operand(T_NONE, .none_lit)); n
type_test = (aux: int, dewy: bool = false) -> int:
    n = node(.istype, operand(T_INT)); nodes[n].aux = i32(aux)
    if dewy: nodes[n].pos = DEWY + n
    n
body = (t: int, bits: int = 0, value: int = 0, valued: bool = true) -> int:
    v = value
    if v == 0: v = operand(t)
    b = node(.block, 0, bits, 0, [node(.exprstmt, v)]); nodes[b].type = i32(t)
    if valued: nodes[b].aux = 1
    if bits & 1 != 0: nodes[b].flags = i32(1073741824)
    b
# A body ending in a statement s: a call (the host decides whether it exits), a jump, a loop.
tail = (s: int, bits: int = 0) -> int:
    b = node(.block, 0, bits, 0, [s]); nodes[b].type = i32(T_VOID); b
call_stmt = (ends: bool) -> int:
    s = node(.exprstmt, operand(T_VOID, .call))
    if ends: nodes[s].ival = 1
    s
branch = (cond: int, b: int, c: int = 0, stmt: bool = false, aux2: int = 0) -> int:
    n = node(.if_, cond); nodes[n].b = i32(b); nodes[n].c = i32(c); nodes[n].aux2 = i32(aux2)
    if stmt: nodes[n].flags = i32(16)
    n
run = (n: int, ex: int = 0):
    t = xf_if(n, ex)
    print("if:{n}:{t}:{int(nodes[n].kind)}:{nodes[n].flags}:{xf_scope.names}:{xf_log}")
run_let = (n: int, ex: int = 0):
    t = xf_iflet(n, ex)
    print("let:{n}:{t}:{nodes[n].a}:{nodes[n].sym}:{xf_scope.names}:{xf_log}")
prepare_conditionals = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_conditionals()
    # Statements: plain tests do not narrow; type tests narrow both ways.
    xf_grow = true
    run(branch(less(), body(T_VOID, 4), 0, true))
    run(branch(type_test(-2), body(T_VOID, 1), 0, true))
    run(branch(type_test(-2), body(T_VOID, 2 | 8), body(T_VOID, 2 | 4), true))
    run(branch(is_none(.ne), body(T_VOID, 3), body(T_VOID, 0), true))
    run(branch(less(), body(T_VOID, 0), body(T_VOID, 1), true))
    # Termination: jumps and never-typed values decide locally; calls and loops ask.
    run(branch(type_test(-2), tail(node(.return_)), tail(call_stmt(false)), true))
    run(branch(type_test(-2), tail(call_stmt(true)), tail(node(.exprstmt, operand(T_NEVER))), true))
    loop_stmt = node(.while_); nodes[loop_stmt].ival = 1
    run(branch(type_test(-2), tail(loop_stmt), tail(node(.continue_)), true))
    nested = branch(less(), tail(node(.break_)), tail(node(.return_)))
    run(branch(type_test(-2), tail(nested), 0, true))
    run(branch(type_test(-2), tail(node(.exprstmt, nested)), 0, true))
    run(branch(type_test(-2), node(.block), 0, true))
    # Fills of optionals: `if v is? none { v = x }` and `if v =? none`.
    xf_fill = 77
    xf_fill_ok = true
    run(branch(type_test(-1), body(T_VOID), body(T_VOID), true))
    run(branch(is_none(.eq), body(T_VOID), 0, true))
    xf_fill_ok = false
    run(branch(is_none(.eq), body(T_VOID), 0, true))
    xf_fill = 0
    # Values: expected types, joins, unions of `?`, never and void branches.
    run(branch(less(), body(T_INT), body(T_INT)), T_FLOAT)
    run(branch(less(), body(T_INT), body(T_STR)))
    run(branch(less(), body(T_INT), body(T_NONE, 0, operand(T_NONE, .none_lit)), false, -8))
    run(branch(less(), body(T_NEVER), body(T_NEVER)))
    run(branch(less(), body(T_NEVER), body(T_INT)), T_FLOAT)
    run(branch(less(), body(T_INT), body(T_NEVER)))
    run(branch(less(), body(T_VOID, 0, 0, false), body(T_INT)))
    run(branch(less(), body(T_INT), body(T_VOID, 0, 0, false)))
    # Container literals: a then-branch literal checked again, an else literal typed by its sibling.
    array_t = int(tb_mk_array(T_INT))
    run(branch(less(), body(array_t, 0, operand(T_INT, .array)), body(array_t)))
    run(branch(less(), body(array_t), body(array_t, 0, operand(T_INT, .array))))
    n = branch(type_test(-2), body(T_INT), body(T_INT))
    xf_sink_at = n
    run(n)
    # Chain ends: the last test of a narrowing chain is a value; else a statement.
    chain = type_test(-3, true)
    run(branch(chain, body(T_INT)), T_INT)
    run(branch(type_test(-3, true), body(T_INT, 0, 0, false)))
    run(branch(type_test(-2, true), body(T_VOID)), T_VOID)
    run(branch(type_test(-2, true), body(T_VOID)))
    # `if let`: optional sources, bindings, statement and value forms.
    opt = int(tb_mk_opt(T_INT))
    n = node(.iflet, operand(opt)); nodes[n].name = 5; nodes[n].b = i32(body(T_INT, 2)); nodes[n].c = i32(body(T_INT))
    run_let(n)
    n = node(.iflet, operand(T_INT)); nodes[n].name = 6; nodes[n].b = i32(body(T_INT)); nodes[n].c = i32(body(T_STR))
    xf_source = operand(opt)
    run_let(n, T_FLOAT)
    n = node(.iflet, operand(opt)); nodes[n].b = i32(body(T_VOID, 4)); nodes[n].flags = i32(16)
    run_let(n)
    n = node(.iflet, operand(opt)); nodes[n].b = i32(body(T_NEVER)); nodes[n].c = i32(body(T_STR))
    run_let(n)
    print(events)
    print(locals.len())
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_conditionals_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_conditionals',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('run(branch(type_test(-2, true), body(T_INT)), T_INT)', 1),
    ('run(branch(less(), body(T_INT)))', 2),
    ('run(branch(less(), body(T_INT), body(T_INT, 0, 0, false)), T_INT)', 3),
    ('n = node(.iflet, operand(T_INT)); nodes[n].b = i32(body(T_INT)); xf_source = operand(T_STR); run_let(n)', 4),
    ('n = node(.iflet, operand(int(tb_mk_opt(T_INT)))); nodes[n].b = i32(body(T_INT)); run_let(n)', 2),
])
def test_checker_conditionals_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_conditionals()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_conditionals',))
    assert output.rstrip().endswith(f':{code}'.encode())
