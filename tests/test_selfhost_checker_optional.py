"""Optional operands retain hints, callback order, rewrites and borrowed arenas."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xo_grow = false
xo_nested = 0
xo_narrowed = 0
xo_exception = false
xo_exact = false
xo_snapshot: Node[]
xo_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xo_grow:
        xo_grow = false
        xo_snapshot = nodes
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); files.push(SrcFile())
        if xo_nested != 0: assert(xo_check(xo_nested, 0, 0).type == T_BOOL)
    int(nodes[n].type)
xo_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xo_narrow_host = (n: int) -> int:
    events.push("narrow:{n}")
    loop i in [0..256): nodes.push(Node()); types.push(TypeInfo())
    xo_narrowed
xo_exception_host = (t: int) -> bool:
    events.push("exceptions:{t}")
    xo_exception
xo_failure_host = (n: int, t: int, expected: int) -> int:
    events.push("failures:{n}:{t}:{expected}")
    nodes[n].kind = .block
    T_STR
xo_exact_host = (n: int) -> bool:
    events.push("exact:{n}")
    xo_exact
xo_error_host = (n: int, t: int, unwrap: bool):
    print("error:{t}:{unwrap}")
    exit(19)
xo_services = CheckerOptionalHost(xo_check_host, xo_coerce_host, xo_narrow_host, xo_exception_host, xo_failure_host, xo_exact_host, xo_error_host)
xo_input = CheckerOptionalInput(&nodes, &types, &files, &T_MATH_INT, &xo_services)
xo_binding = checker_optional_bind(&xo_input)
operand = (t: int) -> int:
    n = node(.ident)
    nodes[n].type = i32(t)
    n
exercise = (kind: NK, left: int, right: int, expected: int, ex: int, wanted: int, bypass: bool = false) -> int:
    n = node(kind, left)
    nodes[n].b = i32(right)
    nodes[n].pos = 1
    result = xo_check(n, expected, ex)
    assert(result.type == wanted and result.bypass == bypass)
    n
main = ():
    prepare()
    opt = int(tb_mk_opt(T_INT))
    boolopt = int(tb_mk_opt(T_BOOL))
    files[0].is_dewy = true
    a = operand(opt)
    b = operand(T_INT)
    start = events.len()
    n = exercise(.coalesce, a, b, 0, 0, T_INT)
    assert(events[start] == "check:{a}:0" and events[start + 1] == "exceptions:{opt}")
    assert(events[start + 2] == "check:{b}:{T_INT}" and events[start + 3] == "coerce:{b}:{T_INT}")
    start = events.len()
    exercise(.unwrap, a, 0, T_INT, T_INT, T_INT)
    assert(events.len() == start + 1 and events[start] == "check:{a}:{opt}")
    start = events.len()
    exercise(.coalesce, a, b, T_INT, T_INT, T_INT)
    assert(events[start] == "check:{a}:{opt}")
    exercise(.coalesce, a, b, opt, opt, T_INT)
    xo_nested = node(.unwrap, operand(boolopt))
    xo_grow = true
    right = operand(opt)
    n = exercise(.coalesce, a, right, 0, 0, opt)
    assert(nodes[n].aux == 1 and xo_snapshot[n].aux == 0)
    xo_narrowed = operand(opt)
    n = exercise(.unwrap, operand(T_INT), 0, 0, 0, T_INT)
    assert(nodes[n].a == i32(xo_narrowed))
    n = exercise(.coalesce, operand(T_INT), operand(T_INT), 0, 0, T_INT)
    assert(nodes[n].a == i32(xo_narrowed))
    xo_exact = true
    n = exercise(.coalesce, a, operand(T_MATH_INT), 0, 0, T_MATH_INT)
    assert(nodes[n].aux == 0)
    xo_exact = false
    exercise(.coalesce, a, operand(T_MATH_INT), 0, 0, T_INT)
    files[0].is_dewy = false
    xo_exception = true
    exercise(.coalesce, a, b, 0, 0, T_INT)
    files[0].is_dewy = true
    n = exercise(.coalesce, a, b, T_BOOL, T_BOOL, T_STR, true)
    assert(nodes[n].kind == .block)
    xo_exception = false
    n = node(.coalesce, a)
    nodes[n].b = i32(b)
    nodes[n].c = 1; nodes[n].pos = 1
    start = events.len()
    assert(xo_check(n, 0, 0).bypass)
    assert(events.len() == start + 2)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_optional_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER,
                   extra_stems=('checker_optional',)).endswith(b'ok\n')


@pytest.mark.parametrize('kind', ['unwrap', 'coalesce'])
def test_checker_optional_errors(compiler, tmp_path, kind):  # noqa: F811
    driver = DRIVER.split('main = ():')[0] + f'''main = ():
    prepare()
    xo_narrowed = operand(T_BOOL)
    exercise(.{kind}, operand(T_INT), operand(T_INT), 0, 0, T_INT)
    assert(false)
'''
    assert compare(compiler, tmp_path, False, driver, 19,
                   extra_stems=('checker_optional',)).startswith(b'error:')
