"""Rare expression diagnostics and zoned-time context agree with the frozen Jo leaf."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_diagnostic_double import diagnostic_status
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'expr_error_context.dewy'
use 'source_types.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'util.jo'
use 'type_ops.dewy'
use 'types.jo'
use 'checker_types.dewy'
use 'checker_state.dewy'
use 'check.jo'
use 'refine.jo'
use 'refine_ops.dewy'
main = ():
    init_types()
    lib_root = "/std/"
    files = [SrcFile(path="case.dewy", src=" use", is_dewy=true), SrcFile(path="/std/time.dewy", src=" type", is_dewy=true)]
    nodes = [Node()]
    decl = mk(.struct_, mkpos(1, 1))
    t = types.len()
    types.push(TypeInfo(kind=.struct_, st=i32(structs.len())))
    structs.push(StructInfo(name="Gap", decl=i32(decl), resolved=true))
    op = args()[1]
    if op == "strings": str_set_unordered(-1, T_INT, str_set_type(["red", "green", "blue", "orange"]))
    if op == "capture":
        nodes[decl].pos = mkpos(0, 1)
        fns = [FnInst(decl=i32(decl))]
        locals = [Local(name=i32(intern("count")), owner=0)]
        implicit_capture_write(0, -1)
    print("scalar:{time_zone_failure(T_INT)}:gap:{time_zone_failure(t)}")
    structs[types[t].st].name = "Ambiguous"
    print("ambiguous:{time_zone_failure(t)}")
    structs[types[t].st].name = "Other"
    print("other:{time_zone_failure(t)}")
    structs[types[t].st].name = "Gap"; nodes[decl].pos = mkpos(0, 1)
    print("user:{time_zone_failure(t)}")
    nodes[decl].pos = mkpos(1, 1); structs[types[t].st].decl = 0
    print("missing:{time_zone_failure(t)}")
    print("policy:{time_policy_why()}")
'''


def test_expr_error_context_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.modules_for

    def modules_for(*args, **kwargs):
        modules = dict(original(*args, **kwargs))
        diagnostic_status(modules)
        modules['diagnostic_exit.dewy'] = modules['diagnostic_exit.dewy'].replace(
            'printl(msg); exit(41)', 'printl("{err_notes.length}: {msg}"); exit(41)')
        return modules

    monkeypatch.setattr(selfhost_lsp_double, 'modules_for', modules_for)
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('expr_error_context',))
    for op, code, expected in [('time', 0, b'scalar:false:gap:true'),
                               ('strings', 41, b"'red' -> 0 'green' -> 1 'blue' -> 2 ..."),
                               ('capture', 41, b"2: this closure changes 'count'")]:
        outputs = [subprocess.run([b, op], capture_output=True, timeout=60) for b in binaries]
        assert all(r.returncode == code for r in outputs), [(r.returncode, r.stderr) for r in outputs]
        assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
        assert expected in outputs[0].stdout
        if op == 'time':
            for expected in (b'ambiguous:true', b'other:false', b'user:false', b'missing:false',
                             b"fold='later' gap='next'"):
                assert expected in outputs[0].stdout
