"""AST construction, child lists, flags and declaration queries match frozen Jo."""

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401


SERVICES = '''use 'node_store.dewy'
nodes: Node[] = [Node()]
lists: i32[]
id_dewy_len = 7
dewy_len_members: {int: int} = {}
dewy_param_kinds: {int: int[]} = {}
'''

DRIVER = '''main = ():
    first = ast_mk(.ident, 11)
    second = ast_mk(.ident, 13)
    tree = ast_mk(.call, 19)
    ast_set_list(tree, [first, first])
    ast_set_list2(tree, [second])
    ast_set_kid(tree, 1, second)
    assert(ast_nkids(tree) == 2 and ast_nkids2(tree) == 1)
    assert(ast_kid(tree, 0) == first and ast_kid(tree, 1) == second and ast_kid2(tree, 0) == second)
    assert(ast_kids(tree) == [first, second] and ast_kids2(tree) == [second])
    nodes[tree].c = i32(first)
    nodes[tree].d = i32(second)
    assert(ast_kid_c(tree) == first and ast_kid_d(tree) == second)
    nodes[tree].kind = .for_
    assert(ast_kid_c(tree) == 0 and ast_kid_d(tree) == 0)
    nodes[tree].kind = .partial
    assert(ast_kid_c(tree) == first and ast_kid_d(tree) == 0)
    nodes[tree].kind = .call
    ast_add_flag(tree, 128 | 0x80000000)
    assert(ast_has_flag(tree, 128) and ast_has_flag(tree, 0x80000000))
    ast_clear_flag(tree, 0x80000000)
    assert(ast_has_flag(tree, 128) and not ast_has_flag(tree, 0x80000000))
    copy = ast_clone(tree)
    assert(copy != tree and ast_kid(copy, 0) != first and not ast_has_flag(copy, 128))
    assert(nodes[ast_kid(copy, 0)].pos == 11 and nodes[ast_kid2(copy, 0)].pos == 13)
    ast_note_member(first)
    assert(not dewy_len_members.has(first))
    nodes[first].name = i32(id_dewy_len)
    ast_note_member(first)
    assert((dewy_len_members.get(first) ?? 0) == 11)
    assert(not ast_decl_has_rest(tree))
    dewy_param_kinds[tree] = [2, 1, 3]
    assert(ast_decl_has_rest(tree))
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_ast_access_twins(compiler, tmp_path, release):
    assert compare_narrow(compiler, tmp_path, release, ('ast_access',), DRIVER,
                          doubles={'services.jo': SERVICES}, services=('ast',)) == b'ok\n'
