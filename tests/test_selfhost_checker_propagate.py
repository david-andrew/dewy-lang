"""`or_throw`: context checks, propagated alternatives and their fit match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
fns: FnInst[] = [FnInst()]
ctxs: FnCtx[]
cx = 0
xq_seen = 0
xq_inferring = false
xq_fits = true
xq_members: int[]
xq_exceptions: int[]
xq_grow = false
xq_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xq_grow:
        xq_grow = false
        loop i in [0..256): nodes.push(Node()); fns.push(FnInst()); ctxs.push(FnCtx())
    xq_seen = n
    int(nodes[n].type)
xq_inferring_host = (inst: int) -> bool:
    events.push("inferring:{inst}")
    xq_inferring
xq_members_host = (t: int) -> int[]:
    events.push("members:{t}")
    xq_members
xq_exception_host = (t: int) -> bool: xq_exceptions.contains(t)
xq_coerce_host = (n: int, from: int, to: int) -> bool:
    events.push("can:{n}:{from}:{to}")
    xq_fits
xq_rewrite_host = (n: int, a: int, exceptions: int[], count: int, expected: int) -> int:
    events.push("rewrite:{n}:{a}:{exceptions}:{count}:{expected}:{nodes[a].flags}")
    T_FLOAT
xq_error_host = (n: int, code: int, t: int, at: int):
    print(events)
    print("error:{n}:{t}:{at}:{code}")
    exit(19)
xq_services = CheckerPropagateHost(xq_check_host, xq_inferring_host, xq_members_host, xq_exception_host, xq_coerce_host, xq_rewrite_host, xq_error_host)
xq_inputs = CheckerPropagateInput(&nodes, &fns, &ctxs, &cx, &xq_seen, &T_NONE, &xq_services)
xq_binding = checker_propagate_bind(&xq_inputs)
propagate = (t: int) -> int:
    v = node(.ident); nodes[v].type = i32(t)
    node(.propagate, v)
run = (n: int, expected: int = 0):
    t = xq_check(n, expected)
    print("{n}:{t}:{int(nodes[n].kind)}")
prepare_propagate = (kind: int, infer: bool) -> int:
    prepare()
    fns.push(FnInst(kind = i32(kind)))
    ctxs.push(FnCtx(inst = i32(fns.len() - 1), ret = i32(T_STR), infer_ret = infer))
    cx = ctxs.len() - 1
    xq_exceptions = [T_NONE, T_FLOAT]
    0
'''

MAIN = r'''
main = ():
    prepare_propagate(0, false)
    xq_grow = true
    xq_members = [T_INT]
    run(propagate(T_INT), T_INT)
    xq_members = [T_INT, T_FLOAT]
    run(propagate(T_INT))
    xq_members = [T_NONE, T_FLOAT]
    run(propagate(T_INT), T_BOOL)
    ctxs[cx].infer_ret = true
    xq_inferring = true
    xq_fits = false
    xq_members = [T_INT, T_FLOAT]
    run(propagate(T_INT))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_propagate_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_propagate',)).endswith(b'ok\n')


@pytest.mark.parametrize('setup,code', [
    ('prepare_propagate(4, false)', 1),
    ('prepare_propagate(0, true)', 1),
    ('prepare_propagate(0, true); xq_inferring = true; xq_members = [T_INT, T_NONE]', 2),
    ('prepare_propagate(0, false); xq_fits = false; xq_members = [T_INT, T_FLOAT]', 3),
])
def test_checker_propagate_errors(compiler, tmp_path, setup, code):  # noqa: F811
    main = f'''
main = ():
    {setup}
    run(propagate(T_INT))
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_propagate',))
    assert output.rstrip().endswith(f':{code}'.encode())
