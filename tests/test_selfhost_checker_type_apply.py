"""`f<T>`: generic function values, bare calls, callable instances and type values match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xa_callee_at = 0
xa_ide_on = false
xa_symbol = 0
xa_kind = 0
xa_bare = false
xa_calls = 1
xa_grow = false
xa_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}:{xa_callee_at}")
    int(nodes[n].type)
xa_lookup_host = (name: int, mod: int, kind: mut int) -> int:
    events.push("lookup:{name}:{mod}")
    kind = xa_kind
    xa_symbol
xa_bare_host = (n: int, callee: bool) -> bool:
    events.push("bare:{n}:{callee}")
    xa_bare
xa_bare_calls_host = (name: int, mod: int) -> int:
    events.push("bare-calls:{name}:{mod}")
    xa_calls
xa_bare_call_host = (n: int, expected: int) -> int:
    events.push("bare-call:{n}:{expected}")
    T_STR
xa_generic_host = (n: int) -> int:
    events.push("generic:{n}")
    if xa_grow:
        xa_grow = false
        loop i in [0..256): nodes.push(Node()); lists.push(0); types.push(TypeInfo())
    int(nodes[n].type)
xa_fn_value_host = (n: int, expected: int, targs: int[], mod: int, closure: int) -> int:
    events.push("fn-value:{n}:{expected}:{targs}:{mod}:{closure}:{nodes[n].name}")
    nodes[n].sym = 55
    T_FLOAT
xa_reference_host = (pos: int, name: int, sym: int): events.push("reference:{pos}:{name}:{sym}")
xa_error_host = (n: int, name: int, code: int):
    print(events)
    print("error:{n}:{name}:{code}")
    exit(19)
xa_services = CheckerTypeApplyHost(xa_check_host, xa_lookup_host, xa_bare_host, xa_bare_calls_host, xa_bare_call_host, xa_generic_host, xa_fn_value_host, xa_reference_host, xa_error_host)
xa_inputs = CheckerTypeApplyInput(&nodes, &lists, &types, &xa_callee_at, &xa_ide_on, &xa_services)
xa_binding = checker_type_apply_bind(&xa_inputs)
targ = (t: int) -> int:
    n = node(.tname, 0, t, 3); nodes[n].type = i32(t); n
apply = (base: int, args: int[]) -> int:
    n = node(.typeapply, base, 0, 0, args); nodes[n].c = i32(node(.tname, 0, T_BOOL, 3)); n
named = (k: NK, name: int, a: int = 0) -> int:
    n = node(k, a); nodes[n].name = i32(name); n
run = (n: int, expected: int = 0):
    r = xa_check(n, expected, expected)
    print("{n}:{r.type}:{r.bypass}:{nodes[n].name}:{xa_callee_at}")
'''

MAIN = r'''
main = ():
    prepare()
    module = int(types.len()); types.push(TypeInfo(kind = .module, mod = 4))
    poly = int(types.len()); types.push(TypeInfo(kind = .polyfn))
    fn_t = int(tb_mk_fn([T_INT], T_INT, 0, 0, 0, false))
    # Generic functions: their value with written arguments, or a bare call.
    xa_symbol = 9; xa_kind = 3
    xa_grow = true
    run(apply(named(.ident, 1), [targ(T_INT), targ(T_STR)]))
    xa_ide_on = true
    m = named(.ident, 7); nodes[m].type = i32(module)
    run(apply(named(.field, 3, m), [targ(T_INT)]))
    xa_ide_on = false
    xa_bare = true
    xa_calls = 2
    run(apply(named(.ident, 1), [targ(T_INT)]), fn_t)
    xa_calls = 1
    run(apply(named(.ident, 1), [targ(T_INT)]))
    xa_bare = false
    # Generic callables held in locals, globals or fields; other bases name types.
    xa_kind = 1
    local = named(.ident, 5); nodes[local].type = i32(poly)
    run(apply(local, [targ(T_INT)]))
    xa_kind = 2
    g = named(.ident, 5); nodes[g].type = i32(poly)
    run(apply(g, [targ(T_STR)]), T_INT)
    held = named(.field, 6, operand_of(T_INT)); nodes[held].type = i32(poly)
    run(apply(held, [targ(T_BOOL)]))
    xa_symbol = 0
    run(apply(named(.ident, 8), [targ(T_INT)]))
    xa_kind = 4; xa_symbol = 3
    run(apply(named(.ident, 8), [targ(T_INT)]))
    print(events)
    print("ok")
'''

HELPERS = r'''
operand_of = (t: int) -> int:
    n = node(.ident); nodes[n].type = i32(t); n
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_type_apply_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + HELPERS + MAIN,
                   extra_stems=('checker_type_apply',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('xa_kind = 3; xa_bare = true; xa_calls = 0; run(apply(named(.ident, 1), []))', 1),
    ('xa_kind = 3; xa_bare = true; xa_calls = 1; run(apply(named(.ident, 1), []), int(tb_mk_fn([T_INT], T_INT, 0, 0, 0, false)))', 2),
    ('xa_kind = 3; xa_bare = true; xa_calls = 0; run(apply(named(.ident, 1), []), int(tb_mk_fn([T_INT], T_INT, 0, 0, 0, false)))', 2),
    ('xa_kind = 1; xa_bare = true; run(apply(named(.ident, 1), []))', 3),
    ('xa_kind = 2; xa_symbol = 9; run(apply(operand_of(T_INT), []))', 4),
])
def test_checker_type_apply_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare()
    xa_symbol = 9
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + HELPERS + main, status=19,
                     extra_stems=('checker_type_apply',))
    assert output.rstrip().endswith(f':{code}'.encode())
