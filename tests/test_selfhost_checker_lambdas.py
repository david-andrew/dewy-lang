"""Lambdas: parameter typing, formals, packs, zonked signatures and instances match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
fns: FnInst[] = [FnInst()]
locals: Local[] = [Local()]
xm_effects_on = false
xm_sink = 0
xm_pack = 0
xm_bound = 0
xm_grow = false
xm_poly_host = (n: int, expected: int) -> int:
    events.push("poly:{n}:{expected}")
    T_STR
xm_base_host = (t: int) -> int:
    events.push("base:{t}")
    t
xm_instance_host = () -> int:
    fns.push(FnInst(kind = 1))
    events.push("instance:{fns.len() - 1}")
    fns.len() - 1
xm_shaped_host = (n: int, f: int, pts: mut int[], mm: int):
    events.push("shaped:{n}:{f}:{pts}:{mm}:{binders.formals}")
    pts[0] = T_FLOAT
xm_entry_host = (n: int, b: int): events.push("entry:{n}:{b}:{binders.formals}:{binders.self}")
# The body gives the expected result (or bool), may give several values, and binds a local.
xm_body_host = (f: int, n: int, hint: int) -> void:
    events.push("body:{f}:{n}:{hint}:{xm_sink}:{fns[f].ptypes}")
    if xm_grow:
        xm_grow = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); fns.push(FnInst()); locals.push(Local()); lists.push(0)
    fns[f].ret = i32(if hint != 0: hint else: T_BOOL)
    fns[f].pack = xm_pack
    locals.push(Local(type = i32(xm_bound)))
    fns[f].locals.push(locals.len() - 1)
xm_zonk_tree_host = (n: int): events.push("zonk-tree:{n}")
xm_labels_host = (n: int) -> int:
    events.push("labels:{n}")
    0
xm_contract_host = (t: int, n: int, zp: int[]) -> int:
    events.push("contract:{t}:{n}:{zp}")
    t
xm_effects_host = (n: int, expected: int) -> int:
    events.push("effects:{n}:{expected}:{nodes[n].type}")
    int(nodes[n].type)
xm_verify_host = (t: int, expected: int, n: int): events.push("verify:{t}:{expected}:{n}")
xm_ownership_host = (t: int, f: int) -> int:
    events.push("ownership:{t}:{f}")
    t
xm_error_host = (n: int, code: int, a: int, b: int):
    print(events)
    print("error:{n}:{a}:{b}:{code}")
    exit(19)
xm_services = CheckerLambdaHost(xm_poly_host, xm_base_host, xm_instance_host, xm_shaped_host, xm_entry_host, xm_body_host, xm_zonk_tree_host, xm_labels_host, xm_contract_host, xm_effects_host, xm_verify_host, xm_ownership_host, xm_error_host)
xm_inputs = CheckerLambdaInput(&nodes, &lists, &types, &args, &fns, &locals, &binders, &refine, &xm_effects_on, &xm_sink, &xm_services)
xm_binding = checker_lambdas_bind(&xm_inputs)
param = (name: int, t: int = 0, flags: int = 0) -> int:
    n = node(.param)
    nodes[n].name = i32(name)
    nodes[n].flags = i32(flags)
    if t != 0: nodes[n].a = i32(node(.tname, 0, t, 3))
    n
lambda = (params: int[], flags: int = 0) -> int:
    n = node(.lambda, 0, 0, 0, params)
    nodes[n].b = i32(node(.block))
    nodes[n].flags = i32(flags)
    n
run = (n: int, expected: int = 0):
    t = xm_lambda(n, expected)
    f = int(nodes[n].sym)
    print("{n}:{t}:{types[t].kind == .fn_}:{f}:{fns[f].decl}:{fns[f].has_env}:{fns[f].ptypes}:{fns[f].ret}:{fns[f].fntype}:{binders.formals}:{binders.self}:{xm_sink}")
prepare_lambdas = ():
    prepare()
    refine = false
'''

MAIN = r'''
main = ():
    prepare_lambdas()
    run(lambda([param(1)], 64), T_INT)
    # Expected function types give parameter types and mutability.
    expected = int(tb_mk_fn([T_INT, T_STR], T_BOOL, 2, 7, 0, false))
    xm_grow = true
    run(lambda([param(1), param(2)]), expected)
    run(lambda([param(1, T_INT), param(2, T_STR, 1)]), expected)
    # Written parameters, refinement formals restored after the body's entry.
    refine = true
    run(lambda([param(3, T_FLOAT), param(4, T_BOOL)]))
    refine = false
    shaped = param(5); nodes[shaped].a = i32(node(.tarray, node(.tname, 0, T_INT, 3), 1))
    run(lambda([shaped]))
    # Several values: the expected pack sets the sink; a compiler-made body is exempt.
    packed = int(tb_mk_fn([], T_INT, 0, 0, 0, true))
    xm_pack = 5
    run(lambda([]), packed)
    run(lambda([], 33554432), expected_none())
    xm_pack = 0
    run(lambda([], 33554432), packed)
    # Zonked signatures and locals; effect rows, contracts and declaration copies.
    v = int(tb_mk_var())
    tu_unify(v, T_STR)
    xm_bound = v
    run(lambda([param(6)]), int(tb_mk_fn([v], v, 0, 0, 0, false)))
    print(locals[locals.len() - 1].type)
    contracted = lambda([param(7, T_INT)]); nodes[contracted].sval = 9
    xm_effects_on = true
    before = nodes.len()
    run(contracted)
    assert(nodes.len() == before + 1 and fns[int(nodes[contracted].sym)].decl == i32(before))
    print(events)
    print("ok")
'''

HELPERS = r'''
expected_none = () -> int: int(tb_mk_fn([], T_INT, 0, 0, 0, false))
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_lambdas_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + HELPERS + MAIN,
                   extra_stems=('checker_lambdas',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('run(lambda([param(1)]), int(tb_mk_fn([T_INT, T_INT], T_INT, 0, 0, 0, false)))', 1),
    ('run(lambda([param(1, T_STR)]), int(tb_mk_fn([T_INT], T_INT, 0, 0, 0, false)))', 2),
    ('run(lambda([param(1)]))', 3),
    ('xm_pack = 3; run(lambda([]), int(tb_mk_fn([], T_INT, 0, 0, 0, false)))', 4),
    ('run(lambda([]), int(tb_mk_fn([], T_INT, 0, 0, 0, true)))', 4),
])
def test_checker_lambdas_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_lambdas()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + HELPERS + main, status=19,
                     extra_stems=('checker_lambdas',))
    assert output.rstrip().endswith(f':{code}'.encode())
