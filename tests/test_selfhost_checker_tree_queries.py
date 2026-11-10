"""Checker name removal and recursive push queries agree across the twin."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'checker_tree_queries.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'util.jo'
use 'check.jo'
main = ():
    nm = intern("items")
    modules = [Module(names={nm: 7}), Module(names={nm: 8})]
    name_first = fill(0, nm + 1); name_first[nm] = 1
    name_mod = [0, 1, 0]; name_sym = [7, 8, 9]; name_next = [2, 3, 0]
    name_unbind(0, nm)
    print("unbind:{modules[0].names.has(nm)}:{modules[1].names.has(nm)}:{name_sym[0]}:{name_sym[1]}:{name_sym[2]}")
    name_unbind(0, nm)
    name_unbind(0, nm + 1)
    nodes = [Node()]
    a = mk(.ident, 0); nodes[a].name = i32(nm)
    f = mk(.field, 0); nodes[f].a = i32(a); nodes[f].name = i32(intern("push"))
    value = mk(.int_lit, 0)
    call = mk(.call, 0); nodes[call].a = i32(f); set_list(call, [value])
    names: {int: bool} = {nm: true}
    print("direct:{pushes_into(call, names)}:none:{pushes_into(0, names)}")
    nodes[f].name = i32(intern("pop")); print("other:{pushes_into(call, names)}"); nodes[f].name = i32(intern("push"))
    names = {}; print("unlisted:{pushes_into(call, names)}"); names = {nm: true}
    parent = mk(.for_, 0); nodes[parent].c = i32(call)
    print("for-c:{pushes_into(parent, names)}")
    nodes[parent].kind = .if_; print("if-c:{pushes_into(parent, names)}")
    nodes[parent].c = 0; set_list(parent, [call]); print("kids:{pushes_into(parent, names)}")
    set_list(parent, []); nodes[parent].b = i32(call); print("child:{pushes_into(parent, names)}")
'''


def test_checker_tree_queries_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('checker_tree_queries',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout == (b'unbind:false:true:0:8:0\ndirect:true:none:false\n'
                                 b'other:false\nunlisted:false\nfor-c:false\nif-c:true\n'
                                 b'kids:true\nchild:true\n')
