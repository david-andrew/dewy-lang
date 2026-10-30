"""Body finalization: zonked types, index/global summaries and write sites match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
fns: FnInst[] = [FnInst()]
locals: Local[] = [Local()]
globals: Global[] = [Global()]
xz_write_sites: int[]
xz_collect_on = false
xz_index_count = 0
xz_global_count = 0
xz_vars = 0
xz_binds = 0
xz_exposures = 0
xz_decls: int[]
xz_prelude_host = (m: int) -> bool:
    events.push("prelude:{m}")
    m == 1
xz_local_error_host = (l: int):
    print(events)
    print("error:{l}:1")
    exit(19)
xz_copy_host = (f: int): events.push("copy:{f}")
xz_definite_host = (b: int, mark: int): events.push("definite:{b}:{mark}")
xz_services = CheckerZonkHost(xz_prelude_host, xz_local_error_host, xz_copy_host, xz_definite_host)
xz_inputs = CheckerZonkInput(&nodes, &lists, &types, &locals, &globals, &fns, &xz_write_sites, &xz_collect_on, &xz_index_count, &xz_global_count, &xz_vars, &xz_binds, &xz_exposures, &xz_decls, &T_MATH_INT, &xz_services)
xz_binding = checker_zonk_bind(&xz_inputs)
typed = (k: NK, t: int, a: int = 0, kids: int[] = []) -> int:
    n = node(k, a, 0, 0, kids); nodes[n].type = i32(t); n
global_ident = (module: int) -> int:
    globals.push(Global(mod = i32(module)))
    n = node(.ident); nodes[n].aux = 2; nodes[n].sym = i32(globals.len() - 1); n
alias_ident = () -> int:
    locals.push(Local(flags = 8))
    n = node(.ident); nodes[n].aux = 1; nodes[n].sym = i32(locals.len() - 1); n
show = (from: int):
    out: str[]
    loop i in [from..nodes.len()): out.push("{nodes[i].type}")
    print(out)
    print("{xz_index_count}:{xz_global_count}:{xz_write_sites}:{xz_collect_on}")
build_body = () -> int:
    v = int(tb_mk_var())
    tu_unify(v, T_STR)
    w = int(tb_mk_var())
    inner = typed(.index, v, global_ident(1))
    lam = typed(.lambda, v, typed(.ident, v))
    loop_body = node(.block, 0, 0, 0, [typed(.assign, w, alias_ident()), node(.break_)])
    f = node(.for_, typed(.ident, v)); nodes[f].b = i32(loop_body); nodes[f].c = i32(typed(.ident, v))
    wh = node(.while_, typed(.bool_lit, T_BOOL)); nodes[wh].b = i32(node(.block, 0, 0, 0, [node(.continue_)]))
    d = typed(.vardecl, v, inner); nodes[d].d = i32(global_ident(3))
    nodes[d].list2 = nodes[node(.block, 0, 0, 0, [typed(.ident, v)])].list; nodes[d].nlist2 = 1
    node(.block, 0, 0, 0, [d, lam, f, wh, node(.return_, global_ident(1)), node(.fn_, typed(.ident, v))])
'''

MAIN = r'''
main = ():
    prepare()
    start = nodes.len()
    root = build_body()
    xz_collect_on = true
    xz_tree(root)
    show(start)
    xz_collect_on = false
    xz_summary(root)
    print("{xz_index_count}:{xz_global_count}")
    xz_summary(node(.block, 0, 0, 0, [global_ident(4), typed(.index, T_INT)]))
    print("{xz_index_count}:{xz_global_count}")
    xz_summary(node(.block, 0, 0, 0, [global_ident(1), alias_ident()]))
    print("{xz_index_count}:{xz_global_count}")
    # Finalization: quiet normal bodies are summarized; others zonked, writes collected
    # for assigned semantic integers; locals zonked.
    body = build_body()
    locals.push(Local(type = i32(T_MATH_INT), flags = 16))
    fns.push(FnInst(body = i32(body), locals = [locals.len() - 1]))
    f = fns.len() - 1
    xz_write_sites = [99]
    xz_collect_on = true
    xz_finalize(f, 0, 0, 0, 0)
    print("{fns[f].write_sites}:{fns[f].writes_ready}:{fns[f].no_indexes}:{fns[f].no_user_globals}:{xz_write_sites}:{xz_collect_on}")
    v = int(tb_mk_var()); tu_unify(v, T_BOOL)
    locals.push(Local(type = i32(v)))
    fns.push(FnInst(body = i32(node(.block, 0, 0, 0, [typed(.ident, T_INT)])), locals = [locals.len() - 1]))
    f = fns.len() - 1
    xz_decls = [1, 2]
    xz_finalize(f, xz_vars, xz_binds, xz_exposures, 1)
    print("{fns[f].write_sites}:{fns[f].writes_ready}:{fns[f].no_indexes}:{fns[f].no_user_globals}:{locals[locals.len() - 1].type}")
    fns.push(FnInst(kind = 1, body = i32(build_body())))
    xz_finalize(fns.len() - 1, xz_vars, xz_binds, xz_exposures, 2)
    print("{fns[fns.len() - 1].no_indexes}:{fns[fns.len() - 1].no_user_globals}:{xz_index_count}:{xz_global_count}")
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_zonk_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_zonk',)).endswith(b'ok\n')


def test_checker_zonk_unresolved_local(compiler, tmp_path):  # noqa: F811
    main = '''
main = ():
    prepare()
    locals.push(Local(type = i32(int(tb_mk_var()))))
    fns.push(FnInst(body = i32(node(.block)), locals = [locals.len() - 1]))
    xz_finalize(fns.len() - 1, 0, 0, 0, 0)
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=('checker_zonk',))
    assert output.rstrip().endswith(b':1')
