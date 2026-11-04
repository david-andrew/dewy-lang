"""Uniqueness-hoisting scan preserves escapes, writes and unknown operations."""
import pytest
from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf, jo_doubles
from tests.test_selfhost_lower_ptr_reads import DRIVER as BASE, JO as BASE_JO

JO = dict(BASE_JO)
JO.update(jo_doubles({'isolation.jo': {
    'isolation_children': 'isolation_children = (k: NK) -> int:\n    if fail_children: print("children-error"); exit(43)\n    if k == .hole: return -1\n    55',
    'isolation_intrinsic': 'isolation_intrinsic = (id: IN) -> bool: id != .syscall',
    'ambient_sharing_stable': 'ambient_sharing_stable = (n: int) -> bool: nodes[n].ival != 99',
}}))
JO['isolation.jo'] = "use 'ast.jo'\nuse 'expr.jo'\nuse 'node_store.dewy'\n" + JO['isolation.jo']
DRIVER = BASE.split('lp_reset =')[0] + r'''
fail_children = false
uq_reset = ():
    uq_written.clear(); uq_escaped.clear(); uq_lambda = false; uq_calls = false
uq_intrinsic = (id: IN, xs: int[]) -> int:
    n = lp_node(.intrinsic, 0, 0, xs); nodes[n].aux = i32(int(id)); n
'''
MAIN = r'''main = ():
    prepare()
    a = lp_local(); b = lp_local(); av = lp_ident(a, T_RAWPTR); bv = lp_ident(b, T_RAWPTR)
    uq_scan(0, 0); assert(uq_written.len() == 0 and uq_escaped.len() == 0)
    uq_scan(av, 1); assert(uq_written.len() == 0 and uq_escaped.len() == 0)
    uq_scan(av, 2); uq_scan(bv, 0); assert(uq_written == [a] and uq_escaped == [b])
    uq_reset(); idx = lp_node(.index, av, bv); uq_scan(idx, 0)
    assert(uq_written.len() == 0 and uq_escaped == [b])
    uq_reset(); nodes[idx].aux = 1; uq_scan(idx, 0); assert(uq_escaped == [a, b]); nodes[idx].aux = 0
    uq_reset(); field = lp_node(.field, av); uq_scan(field, 0); assert(uq_escaped.len() == 0)
    uq_reset(); uq_scan(lp_node(.assign, lp_node(.field, idx), bv), 1)
    assert(uq_written == [a] and uq_escaped == [b, b])
    uq_reset(); uq_target(av); assert(uq_written.len() == 0 and uq_escaped == [a])
    # Loop-element aliases expose the original array instead of the alias.
    alias = lp_local(LF_ELEMALIAS, lp_node(.index, av)); ali = lp_ident(alias, T_INT)
    uq_reset(); uq_scan(ali, 2); assert(uq_escaped == [a] and uq_written.len() == 0)
    # Known length/capacity/in-place operations only read their receiver.
    loop id in [IN.len, IN.arrcap, IN.push, IN.pop, IN.insert, IN.remove, IN.clear, IN.reserve, IN.resize, IN.truncate, IN.extend]:
        uq_reset(); uq_scan(uq_intrinsic(id, [av, bv]), 0)
        assert(uq_escaped == [b] and uq_written.len() == 0)
    uq_reset(); uq_scan(uq_intrinsic(IN.hash, [av, bv]), 0); assert(uq_escaped == [a, b])
    # Unknown operations and lambdas prohibit hoisting, independently of calls.
    loop n in [lp_node(.hole), lp_node(.lambda), uq_intrinsic(IN.syscall, [av])]:
        uq_reset(); uq_scan(n, 1); assert(uq_lambda and uq_escaped.len() == 0)
    uq_reset(); nodes[idx].ival = 99; uq_target(idx)
    assert(uq_calls and uq_written == [a]); nodes[idx].ival = 0
    uq_reset(); nodes[av].ival = 99; uq_scan(av, 1); assert(uq_calls); nodes[av].ival = 0
    # Generic traversals follow a/b/c and both child lists, but never d.
    uq_reset(); n = lp_node(.block, av, bv, [av]); nodes[n].c = i32(bv); nodes[n].d = i32(av)
    node_set_list2(mut nodes, mut lists, n, [bv]); uq_scan(n, 1)
    assert(uq_escaped == [a, b, b, a, b] and not uq_calls and not uq_lambda)
    print("ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_lower_uniqueness_twins(compiler, tmp_path, release):
    out = compare_leaf(compiler, tmp_path, release, DRIVER + MAIN,
                       extra_stems=('lower_uniqueness',), jo_doubles=JO)
    assert out.endswith(b'ok\n')


def test_lower_uniqueness_service_error(compiler, tmp_path):
    driver = DRIVER + 'main = ():\n    prepare(); fail_children = true; uq_scan(lp_node(.int_lit), 0)\n    print("unreachable")\n'
    out = compare_leaf(compiler, tmp_path, False, driver, status=43,
                       extra_stems=('lower_uniqueness',), jo_doubles=JO)
    assert out == b'children-error\n'
