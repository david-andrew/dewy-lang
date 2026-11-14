"""AST captures, converted rest bundles and written/spread arguments match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = '''use 'node_store.dewy'
const NF_GENERIC = 64
nodes: Node[] = [Node()]
lists: i32[]
rest_bundles: {int: int}
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
kids2 = (n: int) -> int[]: node_kids2(nodes, lists, n)
'''
DRIVER = '''main = ():
    body = node_mk(nodes, .block, 0)
    node_set_list(nodes, lists, body, [11, 12])
    f = node_mk(nodes, .lambda, 0)
    node_set_list2(nodes, lists, f, [21, 22])
    assert(lambda_captures(f) == [21, 22])
    nodes[f].flags = 64; nodes[f].d = i32(body)
    assert(lambda_captures(f) == [11, 12])
    empty = node_mk(nodes, .call, 0)
    assert(written_args(empty) == [] and not spreads_rest(empty))
    a = node_mk(nodes, .int_lit, 0)
    rest = node_mk(nodes, .array, 0)
    node_set_list(nodes, lists, rest, [a, a])
    wrap = node_mk(nodes, .conv, 0); nodes[wrap].a = i32(rest)
    twice = node_mk(nodes, .conv, 0); nodes[twice].a = i32(wrap)
    call = node_mk(nodes, .call, 0)
    node_set_list(nodes, lists, call, [a, twice, a])
    assert(rest_bundle_of(twice) == 0)
    rest_bundles[rest] = 2
    saved = written_args(call)
    assert(saved == [a, a, a, a] and not spreads_rest(call))
    rest_bundles[rest] = -1
    assert(rest_bundle_of(twice) == rest and spreads_rest(call))
    node_set_list(nodes, lists, rest, [99])
    assert(written_args(call) == [a, 99, a] and saved == [a, a, a, a])
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_ast_rest_twins(compiler, tmp_path, release):
    assert compare_narrow(compiler, tmp_path, release, ('node_store', 'ast_rest'), DRIVER,
                          doubles={'services.jo': SERVICES}, services=('ast',)) == b'ok\n'
