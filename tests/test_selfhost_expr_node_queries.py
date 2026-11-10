"""Cold receiver and numeric-node queries agree with the frozen Jo leaf."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'expr_node_queries.dewy'
use 'expr.jo'
use 'source_types.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'util.jo'
use 'type_ops.dewy'
use 'types.jo'
use 'checker_state.dewy'
use 'check.jo'
main = ():
    init_types()
    modules = [Module()]
    intrinsics = [Intrinsic("scalar", .assert, false), Intrinsic("each", .assert, true)]
    print("fits:{receiver_fits("scalar", T_INT)}:{receiver_fits("each", T_INT)}:{receiver_fits("each", mk_array(T_INT))}:{receiver_fits("missing", T_INT)}:{receiver_fits("missing", mk_var())}")
    loop t in [T_INT, mk_array(T_INT), T_STR]:
        text = ""
        loop name in fn_names_for(t): text += name_of(name) + ","
        print("names:{text}")
    nodes = [Node()]
    param = mk(.param, 0); decl = mk(.fn_, 0); set_list(decl, [param]); nodes[decl].sym = 1
    decl_infos = [DeclInfo(), DeclInfo(sig=FnSig(done=true, params=[T_INT]))]
    name = intern("custom")
    syms = [Sym(), Sym(kind=.fns, decl=i32(decl))]
    modules[0].names[name] = 1
    print("custom:{receiver_fits("custom", T_INT)}:{receiver_fits("custom", T_STR)}")
    n = mk(.ident, 0)
    print("quat-empty:{is_quat(n)}:group:{grouped_place_call(n)}:{grouped_place_call(0)}")
    quat_nodes[n] = true; print("quat-node:{is_quat(n)}"); quat_nodes = {}
    nodes[n].aux = i32(int(SK.local)); nodes[n].sym = 3
    quat_locals[3] = true; print("quat-local:{is_quat(n)}")
    nodes[n].aux = i32(int(SK.global)); quat_globals[3] = true
    print("quat-global:{is_quat(n)}")
    nodes[n].kind = .int_lit; print("quat-kind:{is_quat(n)}")
'''


def test_expr_node_queries_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('expr_node_queries',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout == (b'fits:true:false:true:false:true\nnames:scalar,\nnames:each,\nnames:each,\n'
                                 b'custom:true:false\nquat-empty:false:group:false:false\nquat-node:true\n'
                                 b'quat-local:true\nquat-global:true\nquat-kind:false\n')
