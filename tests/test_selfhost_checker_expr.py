"""The expression dispatcher: checked nodes, name lookup and kind routing match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_idents import DRIVER as IDENTS
from tests.test_selfhost_checker_resolve import compare

STEMS = ('checker_literals', 'checker_idents', 'checker_conditionals', 'checker_members',
         'checker_indexes', 'checker_receivers', 'checker_variants', 'checker_type_apply',
         'checker_unary', 'checker_logic', 'checker_type_tests', 'checker_optional',
         'checker_aggregates', 'checker_collections', 'checker_cast', 'checker_places',
         'checker_expr')

DRIVER = IDENTS + r'''
syms: Sym[] = [Sym()]
xe_scope = CheckerScope()
xe_at: int[]
xe_mods: int[]
xe_found: int[]
xe_ticks: int[]
xe_struct = 1
xe_sentinel_name = 0
xe_temperature_on = false
xe_values_on = false
xe_watch_counts = StatementWatch()
xe_checked = 0
xe_module_result = 0
xe_grow = false
xe_complete_host = (): events.push("complete")
xe_unknown_host = (n: int, expected: int, name: int):
    print(events)
    print("unknown:{n}:{expected}:{name}")
    exit(19)
xe_module_host = (m: int, name: int) -> int:
    events.push("module:{m}:{name}")
    xe_module_result
xe_temperature_host = (n: int, t: int) -> int:
    events.push("temperature:{n}:{t}")
    T_FLOAT
xe_values_host = (n: int, t: int): events.push("values:{n}:{t}")
xe_binary_host = (n: int, expected: int) -> int:
    events.push("binary:{n}:{expected}")
    if xe_grow:
        xe_grow = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); syms.push(Sym())
        check_expr(node(.int_lit), 0)
    T_FLOAT
xe_call_host = (n: int, expected: int) -> int:
    events.push("call:{n}:{expected}")
    T_STR
xe_sibling_host = (n: int, t: int) -> int:
    events.push("sibling:{n}:{t}")
    t
xe_literal_host = (n: int, expected: int, ex: int) -> int:
    events.push("literal:{n}:{expected}:{ex}")
    ex
xe_other_host = (n: int, expected: int) -> int:
    events.push("other:{n}:{int(nodes[n].kind)}:{expected}")
    T_BOOL
xe_services = CheckerExprHost(xe_complete_host, xe_unknown_host, xe_module_host, xe_temperature_host, xe_values_host, xe_binary_host, xe_call_host, xe_sibling_host, xe_literal_host, xe_other_host)
xe_inputs = CheckerExprInput(&nodes, &syms, &xe_scope, &ctxs, &cx, &xe_at, &xe_mods, &xe_found, &xe_ticks, &xe_struct, &xe_sentinel_name, &xe_temperature_on, &xe_values_on, &xe_watch_counts, &xe_checked, &xe_services)
xe_binding = checker_expr_bind(&xe_inputs)
sym_of = (kind: SK, ref: int) -> int:
    syms.push(Sym(name = 2, kind = kind, ref = i32(ref)))
    syms.len() - 1
# Name 2 bound in scope at index i, to symbol s.
scoped = (s: int, at: int):
    loop xe_scope.syms.len() <= at: xe_scope.syms.push(0)
    xe_scope.syms[at] = s
    loop xe_scope.top.len() <= 2: xe_scope.top.push(-1)
    xe_scope.top[2] = at
cached = (m: int, s: int, stamp: int):
    loop xe_at.len() <= 2: xe_at.push(0); xe_mods.push(0); xe_found.push(0)
    xe_at[2] = stamp; xe_mods[2] = m; xe_found[2] = s
show = (n: int, expected: int = 0):
    t = check_expr(n, expected)
    print("{n}:{t}:{xe_checked}:{int(nodes[n].kind)}:{nodes[n].type}:{nodes[n].aux}:{nodes[n].sym}:{int(nodes[n].flags)}")
prepare_expr = ():
    prepare_idents()
'''

MAIN = r'''
main = ():
    prepare_expr()
    own = local_of(T_INT, 1)
    # A checked node keeps its type; an unchecked one is routed by kind.
    n = node(.binary); nodes[n].type = i32(T_U8); nodes[n].flags = 128
    show(n)
    nodes[n].flags = 0
    show(n, T_INT)
    show(node(.call), T_INT)
    show(node(.int_lit))
    show(node(.int_lit), T_FLOAT)
    show(node(.bool_lit))
    show(node(.float_lit), T_FLOAT)
    show(node(.str_lit))
    loop k in [NK.lambda, NK.block, NK.match_, NK.range, NK.propagate, NK.intrinsic, NK.vardecl]: show(node(k), T_INT)
    # Binary checking may grow every arena and reenter before the result is published.
    xe_grow = true
    n = node(.binary)
    show(n, T_INT)
    assert(not xe_grow and nodes[n].type == i32(T_FLOAT))
    # Names: the scope above the function's floor, else the module cache, else the host.
    scoped(sym_of(.local, own), 4)
    show(name_node())
    ctxs[cx].floor = 5
    g = sym_of(.local, own)
    cached(int(ctxs[cx].mod), g, 1)
    show(name_node())
    xe_ticks = [0, 0, 7]
    xe_module_result = g
    show(name_node())
    xe_at[2] = 7
    show(name_node())
    xe_mods[2] = 5
    show(name_node())
    xe_mods[2] = int(ctxs[cx].mod)
    xe_ticks = [0, 0, 0]
    xe_struct = 7
    show(name_node())
    # Outside every function: no floor, the module -1; a module name, which reads no context.
    cx = -1
    xe_mods[2] = -1
    xe_found[2] = sym_of(.module, 0)
    xe_scope.top[2] = -1
    show(name_node())
    cx = 1
    ctxs[cx].floor = 0
    # Every symbol kind reaches the identifier leaf with its frozen ordinal.
    loop k in [SK.global, SK.fns, SK.struct_, SK.enum_, SK.const_, SK.module, SK.type_, SK.alias_]:
        globals.push(Global(type = i32(T_INT), state = 2))
        scoped(sym_of(k, globals.len() - 1), 4)
        show(name_node(), T_INT)
    # Rare tables, completion, temperatures and several values.
    scoped(sym_of(.local, own), 4)
    xe_watch_counts.const_views = 1
    xe_watch_counts.decimal_globals = 2
    show(name_node())
    xe_watch_counts.const_views = 0
    xe_watch_counts.decimal_globals = 0
    xe_sentinel_name = 2
    show(name_node())
    xe_sentinel_name = 3
    show(name_node())
    xe_temperature_on = true
    xe_values_on = true
    show(name_node())
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_expr_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=STEMS).endswith(b'ok\n')


@pytest.mark.parametrize('setup', ['xe_module_result = 0', 'ctxs[cx].floor = 9'])
def test_checker_expr_unknown_names(compiler, tmp_path, setup):  # noqa: F811
    main = f'''
main = ():
    prepare_expr()
    scoped(sym_of(.local, local_of(T_INT, 1)), 4)
    {setup}
    if ctxs[cx].floor == 0: xe_scope.top[2] = -1
    show(name_node())
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=STEMS)
    assert b'unknown:' in output and b'module:' in output
