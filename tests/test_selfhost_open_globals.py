"""Open global finalization resolves metadata and preserves pending instances agree with the frozen Jo leaf."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_diagnostic_double import diagnostic_status
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'open_globals.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'util.jo'
main = ():
    init_types()
    nodes = [Node()]
    v = mk_var(); arr = mk_array(v); ptr = mk_ptr(v)
    decl = mk(.vardecl, 7); nodes[decl].type = i32(v)
    init = mk(.int_lit, 7); nodes[init].type = i32(v); nodes[decl].b = i32(init)
    body = mk(.int_lit, 7); nodes[body].type = i32(v)
    globals = [Global(name=i32(intern("items")), type=i32(arr), decl=i32(decl)), Global(type=i32(ptr)), Global()]
    open_globals = [0]
    locals = [Local(type=i32(v)), Local(type=i32(v))]
    ft = mk_fn([v], v, 0)
    fns = [FnInst(), FnInst(body=i32(body), state=2, locals=[0], ptypes=[v], targs=[arr], ret=i32(v), fntype=i32(ft)), FnInst(state=1, locals=[1], ptypes=[v], ret=i32(v))]
    if args()[1] == "unresolved":
        ts_dewy = true
        settle_open_globals()
    unify(v, T_INT)
    settle_open_globals()
    print("globals:{type_eq(int(globals[0].type), mk_array(T_INT))}:{type_eq(int(globals[1].type), mk_ptr(T_INT))}:{globals[2].type}")
    print("nodes:{nodes[decl].type == i32(T_INT)}:{nodes[init].type == i32(T_INT)}:{nodes[body].type == i32(T_INT)}")
    print("fn:{locals[0].type == i32(T_INT)}:{fns[1].ptypes[0] == T_INT}:{type_eq(fns[1].targs[0], mk_array(T_INT))}:{fns[1].ret == i32(T_INT)}:{type_eq(int(fns[1].fntype), mk_fn([T_INT], T_INT, 0))}")
    print("pending:{locals[1].type == i32(v)}:{fns[2].ptypes[0] == v}:{fns[2].ret == i32(v)}")
'''


def test_open_globals_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.modules_for

    def modules_for(*args, **kwargs):
        modules = dict(original(*args, **kwargs))
        diagnostic_status(modules)
        return modules

    monkeypatch.setattr(selfhost_lsp_double, 'modules_for', modules_for)
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('open_globals',))
    for op, code, expected in [('resolved', 0, b'globals:true:true:0'),
                               ('unresolved', 41, b"cannot infer the type of 'items'")]:
        outputs = [subprocess.run([b, op], capture_output=True, timeout=60) for b in binaries]
        assert all(r.returncode == code for r in outputs), [(r.returncode, r.stderr) for r in outputs]
        assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
        assert expected in outputs[0].stdout
        if op == 'resolved':
            assert b'nodes:true:true:true' in outputs[0].stdout
            assert b'fn:true:true:true:true:true' in outputs[0].stdout
            assert b'pending:true:true:true' in outputs[0].stdout
