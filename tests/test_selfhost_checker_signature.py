"""Signature publication retains scope, binders and stable IDs under reentry."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
declarations: DeclInfo[] = [DeclInfo()]
sig_depth = 0
nested_decl = 0
sig_grow = true
sig_snapshot = FnSig()
sig_nodes: Node[]
sig_declarations: DeclInfo[]
sig_resume = (d: int): events.push("sig-resume:{d}")
sig_enter = (d: int) -> CheckerSignatureScope:
    saved = sig_depth
    sig_depth += 1
    events.push("sig-enter:{d}:{binders.formals}:{binders.self}")
    CheckerSignatureScope(saved, d)
sig_leave = (scope: CheckerSignatureScope):
    assert(sig_depth == scope.context + 1)
    sig_depth = scope.context
    events.push("sig-leave:{scope.mark}:{binders.formals}:{binders.self}")
sig_finish = (d: int, sig: mut FnSig, shaped: bool, mask: int):
    assert(sig.done and binders.self == 0)
    if sig.params.len() == 40: assert(mask == (1 << 40) - 1 and sig.mutmask == -1, "validation keeps the full word mask")
    events.push("sig-finish:{d}:{sig.params}:{sig.ret}:{sig.ntp}:{sig.nexplicit}:{sig.mutmask}:{shaped}:{binders.formals}")
    if sig_grow:
        sig_grow = false
        sig_snapshot = sig
        sig_nodes = nodes
        sig_declarations = declarations
        loop i in [0..128): nodes.push(Node()); declarations.push(DeclInfo())
        saved = binders.formals
        nested = cs_fn_sig(nested_decl)
        assert(binders.formals == saved and binders.self == 0 and nested.ret == i32(T_VOID))
        sig.contract = 456
        sig.params.push(T_BOOL)
    if shaped: sig.ret = i32(T_STR)
sig_host = CheckerSignatureHost(sig_resume, sig_enter, sig_leave, sig_finish)
sig_input = CheckerSignatureInput(&nodes, &lists, &declarations, &binders, &refine, &T_VOID, &sig_host)
sig_binding = checker_signature_bind(&sig_input)
main = ():
    prepare()
    it = node(.tname, 0, T_INT, 3)
    shaped = node(.tarray, it, 1)
    pa = node(.param, shaped); nodes[pa].name = 1; nodes[pa].flags = 1
    pb = node(.param); nodes[pb].name = 2
    nested_decl = node(.lambda)
    nodes[nested_decl].flags = 4194304
    decl = node(.fn_, it, 0, 0, [pa, pb], [it])
    saved_nodes = nodes
    saved_declarations = declarations
    result = cs_fn_sig(decl)
    assert(result.done and result.generic and result.ntp == 2 and result.nexplicit == 1)
    assert(result.mutmask == 1 and result.ret == i32(T_STR) and result.contract == 456)
    assert(result.params.len() == 3 and sig_snapshot.params.len() == 2 and sig_snapshot.contract == 0)
    assert(saved_nodes[decl].sym == 0 and saved_declarations.len() == 1)
    di = int(nodes[decl].sym)
    assert(not sig_declarations[di].sig.done and declarations[di].sig.done)
    assert(binders.formals == [88] and binders.self == 77 and sig_depth == 0)
    count = events.len()
    assert(cs_fn_sig(decl) == result and events.len() == count)
    result.params.push(T_FLOAT)
    assert(cs_fn_sig(decl).params.len() == 3, "returned signatures preserve cache snapshots")
    refine = false
    plain = node(.fn_, 0, 0, 0, [node(.param, it)])
    result = cs_fn_sig(plain)
    assert(not result.generic and result.ntp == 0 and result.ret == 0 and result.params == [T_INT])
    assert(binders.formals == [88] and binders.self == 77)
    widep = node(.param, it); nodes[widep].flags = 1
    wideps: int[]
    loop i in [0..40): wideps.push(widep)
    wide = cs_fn_sig(node(.fn_, 0, 0, 0, wideps))
    assert(wide.mutmask == -1)
    r = node(.trefined)
    assert(cs_written_refinement(r) and cs_written_refinement(shaped))
    assert(cs_written_refinement(node(.tmap, 0, 0, 1)))
    p = node(.param); nodes[p].b = i32(r)
    assert(not cs_written_refinement(p), "parameter defaults do not activate refinements")
    nodes[p].a = i32(r)
    assert(cs_written_refinement(p))
    assert(not cs_written_refinement(node(.lambda, r)) and not cs_written_refinement(node(.block, r)))
    assert(cs_written_refinement(node(.fn_, 0, 0, 0, [p])))
    assert(not cs_written_refinement(0))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_signature_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER,
                   extra_stems=('checker_signature',)).endswith(b'ok\n')
