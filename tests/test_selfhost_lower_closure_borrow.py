"""Closure invocation/forwarding summaries match their frozen Jo implementation."""
import pytest
from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf, jo_doubles
from tests.test_selfhost_lower_ptr_reads import DRIVER as BASE, JO as BASE_JO

JO = dict(BASE_JO)
JO.update(jo_doubles({
    'copies.jo': {'copy_consumes': 'copy_consumes = (f: int, i: int) -> bool:\n    if fail_copy: print("copy-error"); exit(42)\n    consumes'},
    'util.jo': {'name_of': 'name_of = (n: int) -> str: names[n]', 'pos_file': 'pos_file = (p: int) -> int: 0'},
}))
JO['ast.jo'] += 'const NF_GENERIC = 8192\n'
DRIVER = BASE.split('lp_reset =')[0] + r'''
struct CBModule:
    is_prelude: bool
modules: CBModule[] = [CBModule()]
consumes = false
fail_copy = false
cb_invoke = (n: int) -> int:
    c = lp_node(.call, n); nodes[c].aux = 1; c
cb_lambda = (body: int, outer: int, inner: int) -> int:
    f = lp_fn(body); fns[f].caps = [Capture(i32(outer), i32(inner))]
    n = lp_node(.lambda); nodes[n].sym = i32(f); n
'''
JO['check.jo'] += 'struct CBModule:\n    is_prelude: bool\nmodules: CBModule[] = [CBModule()]\n'
JO['util.jo'] += "use 'source_types.dewy'\n"
JO['util.jo'] += 'files: SrcFile[] = [SrcFile()]\n'
DRIVER = DRIVER.replace('struct CBModule:\n    is_prelude: bool\nmodules: CBModule[] = [CBModule()]\n', '')
DRIVER = "use 'util.jo'\nuse 'copies.jo'\n" + DRIVER.replace('files: SrcFile[] = [SrcFile()]\n', '')

MAIN = r'''main = ():
    prepare(); files[0].is_dewy = false
    p = lp_local(); ident = lp_ident(p, T_INT)
    f = lp_fn(cb_invoke(ident), [p])
    assert(closure_borrow_param(f, 0) and stack_closure_params[p])
    assert(closure_invoked_only(0, p) and closure_invoked_only(lp_node(.fn_, ident), p))
    assert(not closure_invoked_only(ident, p) and closure_invoked_only(ident, p, true))
    assert(not closure_invoked_only(lp_node(.return_, ident), p))
    assert(not closure_borrow_param(0, 0) and not closure_borrow_param(f, 1))
    fns[f].cabi = true; assert(not closure_borrow_param(f, 0)); fns[f].cabi = false
    saved = fns[f].decl; fns[f].decl = 0; assert(not closure_borrow_param(f, 0)); fns[f].decl = saved
    consumes = true; assert(not closure_borrow_param(f, 0)); consumes = false
    # Named forwarding proves the callee parameter; recursion defaults to false.
    q = lp_local(); qi = lp_ident(q, T_INT)
    forwarding = lp_fn(lp_call(f, [qi]), [q])
    assert(closure_borrow_param(forwarding, 0))
    stack_closure_params.clear()
    fns[f].body = i32(lp_call(forwarding, [ident]))
    assert(not closure_borrow_param(f, 0) and not stack_closure_params[p])
    # A called lambda may borrow immutable captures; escaping/mutating ones cannot.
    inner = lp_local(); ii = lp_ident(inner, T_INT)
    lam = cb_lambda(cb_invoke(ii), p, inner)
    assert(closure_invoked_only(lam, p, true) and not closure_invoked_only(lam, p))
    assert(closure_invoked_only(cb_invoke(lam), p))
    loop flag in [LF_ASSIGNED, LF_ADDR, LF_EXPOSED, LF_SHARED]:
        locals[inner].flags = i32(flag); assert(not closure_invoked_only(lam, p, true))
    locals[inner].flags = 0
    nodes[lam].flags = i32(NF_GENERIC); assert(not closure_invoked_only(lam, p, true)); nodes[lam].flags = 0
    nodes[lam].sym = 0; assert(not closure_invoked_only(lam, p, true))
    # Formal parameter permission and mutation flags fail closed.
    loop flag in [LF_MUTPARAM, LF_ASSIGNED, LF_ADDR, LF_EXPOSED]:
        stack_closure_params.clear(); locals[p].flags = i32(flag)
        assert(not closure_borrow_param(f, 0))
    locals[p].flags = 0
    # Dewy formals are read through their generated local binding.
    stack_closure_params.clear(); files[0].is_dewy = true
    local = lp_local(); li = lp_ident(local, T_INT)
    bind = lp_node(.vardecl, 0, ident); nodes[bind].sym = i32(local); nodes[bind].aux2 = 1
    fns[f].body = i32(lp_node(.block, 0, 0, [bind, cb_invoke(li)]))
    assert(closure_borrow_param(f, 0))
    stack_closure_params.clear(); locals[local].flags = i32(LF_SHARED)
    assert(not closure_borrow_param(f, 0)); locals[local].flags = 0
    stack_closure_params.clear(); nodes[bind].aux2 = 0
    assert(not closure_borrow_param(f, 0)); nodes[bind].aux2 = 1
    stack_closure_params.clear(); fns[f].body = i32(lp_node(.block, 0, 0, [bind, lp_node(.return_, li)]))
    assert(not closure_borrow_param(f, 0))
    # The existing scoped fork-join contract remains a special case.
    fns[f].params = [q, p]; modules[0].is_prelude = true
    names.push("__parallel_run"); nodes[int(fns[f].decl)].name = i32(names.len() - 1)
    assert(closure_borrow_param(f, 1))
    modules[0].is_prelude = false; assert(not closure_borrow_param(f, 1))
    print("ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_lower_closure_borrow_twins(compiler, tmp_path, release):
    out = compare_leaf(compiler, tmp_path, release, DRIVER + MAIN,
                       extra_stems=('lower_closure_borrow',), jo_doubles=JO)
    assert out.endswith(b'ok\n')


def test_lower_closure_borrow_service_error(compiler, tmp_path):
    driver = DRIVER + 'main = ():\n    prepare(); fail_copy = true; p = lp_local(); closure_borrow_param(lp_fn(0, [p]), 0)\n    print("unreachable")\n'
    out = compare_leaf(compiler, tmp_path, False, driver, status=42,
                       extra_stems=('lower_closure_borrow',), jo_doubles=JO)
    assert out == b'copy-error\n'
