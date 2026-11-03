"""check_call_expr in the expression dispatcher's leaf: the paths before the pick and the
picked function's obligations after it."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_call_args import DRIVER as CALL_ARGS
from tests.test_selfhost_checker_expr import JO_DOUBLES, STEMS

DRIVER = CALL_ARGS + r'''
use 'concurrency.jo'
zh_habits: int[] = [3, 0, 0, 0, 0, 0, 0, 0, 0]
zh_input = CheckerCallQueryInput(&nodes, &lists, &files, &cq_names, &cq_set, &fns, &cq_float_names, &cq_host, &syms, &names, &cq_family, &cq_family, &cq_family, &cq_family, &cq_family, &zh_habits)
zh_binding = checker_call_queries_bind(&zh_input)
# An unchecked call of callee named name with args, in a Dewy file unless jo.
call = (name: int, args: int[], jo: bool = false) -> int:
    callee = done(T_INT); nodes[callee].name = i32(name)
    n = node(.call, callee, 0, 0, args)
    nodes[n].flags = 0
    nodes[n].pos = (if jo: 2 else: 1) << 40
    nodes[n].pos += n
    n
fn_with = (atomic: bool, task: bool, parallel: bool, pack: int) -> int:
    fns.push(FnInst(atomic_api = atomic, task_api = task, parallel_api = parallel, pack = pack))
    fns.len() - 1
# An unchecked call whose callee is a node of kind k.
headed = (k: NK) -> int:
    n = call(3, [done(T_INT)])
    nodes[int(nodes[n].a)].kind = k
    n
picked = (n: int, f: int, aux: int = 0) -> int:
    nodes[n].sym = i32(f); nodes[n].aux = i32(aux); n
'''

MAIN = r'''
main = ():
    prepare_expr()
    loop names.len() < 32: names.push("f{names.len()}")
    names[20] = "__shape_value"; names[21] = "__map_of"
    files.push(SrcFile(is_dewy = false))
    # The picked function's obligations: atomic and task entry points, parallel pairs, packs.
    show(picked(call(3, [done(T_INT)]), fn_with(true, true, false, 0)))
    print("tasks:{concurrency_tasks}:{concurrency_runtime_needed}")
    show(picked(call(3, [done(T_INT), done(T_INT)]), fn_with(false, false, true, 0)))
    show(picked(call(3, [done(T_INT)]), fn_with(false, false, true, 1)))
    print("parallel:{concurrency_calls}")
    pack_t = int(tb_mk_fn([T_INT], T_INT, 0, 0, 0, true))
    value_call = picked(call(3, [done(T_INT)]), 0, 1)
    nodes[int(nodes[value_call].a)].type = i32(pack_t)
    show(value_call)
    zc_base = int(tb_mk_fn([T_INT], T_INT, 0))
    show(value_call)
    zc_base = 0
    # (a Jo file's give form; a call the pick replaced keeps none of these)
    show(picked(call(3, [done(T_INT), done(T_INT)], true), fn_with(true, false, false, 0), 2))
    zc_rekind = true
    show(picked(call(3, [done(T_INT)]), fn_with(true, true, false, 1)))
    zc_rekind = false
    # Before the pick: elementwise calls, big integer literals, partial evaluation.
    broadcast = call(3, [done(T_INT)]); nodes[broadcast].flags = 16384
    show(broadcast, T_INT)
    big = call(3, [done(T_INT)]); nodes[big].aux2 = -1
    zc_literal = int(T_MATH_INT)
    show(big)
    big = call(3, [done(T_INT)]); nodes[big].aux2 = -1
    zc_literal = -1
    show(big, T_INT)
    partial = call(3, [done(T_INT)]); nodes[partial].aux2 = -10
    show(partial, T_INT)
    nodes[partial].flags = 536870912; zc_numeric = true
    show(partial, T_INT)
    zc_numeric = false
    # Values to expand: an argument that spreads asks values_call first.
    spread = done(T_INT); nodes[spread].flags = i32(128 | 1024)
    zc_values = int(T_BOOL)
    show(call(3, [spread]))
    zc_values = -1
    show(call(3, [spread]))
    numeric = call(3, [spread]); nodes[numeric].flags = 536870912; zc_numeric = true
    show(numeric)
    zc_numeric = false
    # Destination hints: a generated shape check's value, a map's rows.
    arr = int(tb_mk_array(T_INT))
    shape = call(20, [done(arr), done(T_INT)])
    show(shape, arr)
    print("shape-kid:{lists[int(nodes[shape].list)]}")
    show(call(20, [done(arr), done(T_INT)]), T_INT)
    zc_nd = true
    show(call(20, [done(arr), done(T_INT)]), T_INT)
    zc_nd = false
    show(call(21, [done(T_INT)]), T_INT)
    show(call(21, [done(T_INT)]))
    # check_call: the head checks, then the callee's kind; a name is picked here.
    zc_head = int(T_BOOL)
    show(call(3, [done(T_INT)]))
    zc_head = -1
    zc_special = int(T_BOOL)
    show(call(3, [done(T_INT)]))
    zc_special = -1
    zc_module = 6
    show(call(3, [done(T_INT)]))
    zc_module = -1
    # (outside the library a habit-named call is asked about: name 3 is the first habit's)
    zc_lib = false
    show(call(3, [done(T_INT), done(T_INT)]))
    show(call(3, [done(T_INT), done(T_INT), done(T_INT), done(T_INT)]))
    zc_lib = true
    loop k in [NK.typeapply, NK.dotname, NK.field, NK.index, NK.call]: show(headed(k))
    zc_index = int(T_BOOL)
    show(headed(.index))
    zc_index = -1
    # call_by_name: the library's rewrites, intrinsics (a hidden assert among them), the
    # name's symbol, its families, then the pick or, with none, the unknown-call service.
    zn_early = int(T_BOOL)
    show(call(4, [done(T_INT)]))
    show(call(4, [done(T_INT), done(T_INT)]))
    zn_early = -1
    # (name 4 is intrinsic 5 here)
    cq_names = [0, 0, 0, 0, 6]
    show(call(4, [done(T_INT)]))
    zn_array = int(T_BOOL)
    show(call(4, [done(T_INT)]))
    show(call(4, []))
    zn_array = -1
    zn_hidden = true
    zn_decls = false
    show(call(4, [done(T_INT)]))
    zn_hidden = false
    show(call(4, [done(T_INT)]))
    cq_names = [0]
    zn_builtin = true
    show(call(4, [done(T_INT)]))
    zn_builtin = false
    zn_decls = true
    zc_module = 6
    show(call(4, [done(T_INT)]))
    zn_module_sym = sym_of(.struct_, 0)
    show(call(4, [done(T_INT), done(T_INT)]))
    zn_sym = int(T_BOOL)
    show(call(4, [done(T_INT)]))
    zn_sym = -1
    zn_module_sym = sym_of(.fns, 0)
    show(call(4, [done(T_INT)]))
    show(call(4, [done(T_INT), done(T_INT)]))
    show(call(21, [done(T_INT), done(T_INT)]))
    show(call(22, [done(T_INT), done(T_INT), done(T_INT)]))
    zn_module_sym = 0
    zc_module = -1
    zn_collect = int(T_U64)
    show(call(4, [done(T_INT)]))
    zn_collect = -1
    # (a method call: no symbol, families by receiver)
    print("ufcs:{call_by_name(call(4, [done(T_INT)]), 4, -1, [done(T_INT)], 0, true)}")
    print("ufcs:{call_by_name(call(4, [done(T_INT)]), 4, 6, [done(T_INT), done(T_INT)], 0, true)}")
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_call_expr_twins(compiler, tmp_path, release):  # noqa: F811
    from tests.test_selfhost_checker_resolve import compare
    assert compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=STEMS, jo_doubles=JO_DOUBLES).endswith(b'ok\n')


def test_checker_call_expr_literal_first(compiler, tmp_path):  # noqa: F811
    # A big integer literal's call form is answered before anything else about the call.
    from tests.test_selfhost_checker_resolve import compare
    main = r'''
main = ():
    prepare_expr()
    big = call(3, [done(T_INT)]); nodes[big].aux2 = -1; nodes[big].flags = 16384
    zc_literal = -2
    check_expr(big, T_INT)
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=STEMS, jo_doubles=JO_DOUBLES)
    assert output.startswith(b'literal-error:') and b'unreachable' not in output


@pytest.mark.parametrize('ufcs', ['false', 'true'])
def test_checker_call_expr_unknown_name(compiler, tmp_path, ufcs):  # noqa: F811
    # A name with no function: the unknown-call service's diagnostic, after the symbol's turn.
    from tests.test_selfhost_checker_resolve import compare
    main = f'''
main = ():
    prepare_expr()
    zn_decls = false
    zn_fatal = true
    n = call(4, [done(T_INT)])
    call_by_name(n, 4, -1, [done(T_INT)], 0, {ufcs})
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=STEMS, jo_doubles=JO_DOUBLES)
    assert b'unknown-call:4' in output and b'unreachable' not in output
