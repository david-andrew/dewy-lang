"""Loop breaks respect depth and closure scope, and place chains resolve to their root."""
import subprocess

from tests import selfhost_lsp_double
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = """use 'main.jo'
use 'checker_tree_queries.dewy'
use 'ast.jo'
use 'node_store.dewy'
main = ():
    nodes = [Node()]
    b = mk(.break_, 0)
    blk = mk(.block, 0); set_list(blk, [b])
    w = mk(.while_, 0); nodes[w].b = i32(blk)
    print("{has_break(0)}:{has_break(blk)}:{has_break(w)}")
    nodes[b].ival = 1
    print("{has_break(w)}:{has_break(blk, 1)}")
    lam = mk(.lambda, 0); nodes[lam].b = i32(w)
    print(has_break(lam))
    nodes[b].ival = 0; nodes[w].b = 0; nodes[w].a = i32(b)
    print(has_break(w))
    name = mk(.ident, 0)
    field = mk(.field, 0); nodes[field].a = i32(name)
    index = mk(.index, 0); nodes[index].a = i32(field)
    print("{place_root(index) == name}:{place_root(name) == name}:{place_root(0)}:{place_root(blk)}")
"""


def test_checker_tree_queries_breaks_and_place_roots(compiler, tmp_path, monkeypatch):
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('checker_tree_queries',)):
        result = subprocess.run([binary], check=True, capture_output=True, timeout=60)
        assert result.stdout == b'false:true:false\ntrue:true\nfalse\ntrue\ntrue:true:0:0\n'
