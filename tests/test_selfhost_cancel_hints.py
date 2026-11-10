"""Cancellation source excerpts and diagnostic paths agree with the frozen Jo leaf."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_diagnostic_double import diagnostic_status
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'cancel_hints.dewy'
use 'source_types.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'util.jo'
main = ():
    files = [SrcFile(path="case.dewy", src=" items...", is_dewy=true), SrcFile(path="other.dewy", src="other", is_dewy=true)]
    nodes = [Node()]
    a = mk(.ident, mkpos(0, 1))
    b = mk(.ident, mkpos(0, 3))
    other = mk(.ident, mkpos(1, 0))
    n = mk(.call, mkpos(0, 2)); nodes[n].a = i32(a); nodes[n].b = i32(b); nodes[n].c = i32(other)
    op = args()[1]
    if op == "spread": cancel_reject(a, false, "this collector")
    if op == "coalesce": cancel_reject(a, true, "this value")
    if op == "replace": cancel_reject(a, false, "this `??`")
    if op == "parallel":
        files[0].src = " parallel loop x in xs x"
        cancel_reject(a, false, "this collector")
    print("bounds:{pos_off(cancel_first_pos(n, 0, 0))}:{pos_off(cancel_last_pos(n, 0, 0))}")
    set_list(n, [b])
    print("kids:{pos_off(cancel_last_pos(n, 0, 0))}")
    loop text in ["items...", "call(\"a b\", [x]) ??", "x; next", "x\nnext", "parallel loop", "parallelx loop", "(x\ny)", "'a\\' b' ?"]:
        files[0].src = " " + text
        print("text:{cancel_text(a)}:parallel:{cancel_parallel_at(nodes[a].pos)}")
    files[0].src = " x" + byte_str(255) + " ?"
    print("raw:{cancel_text(a)}")
    files[0].src = " xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    print("long:{cancel_text(a)}")
    nodes[a].pos = 0
    print("missing:{cancel_text(a)}:{cancel_parallel_at(0)}")
'''


def test_cancel_hints_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.modules_for

    def modules_for(*args, **kwargs):
        modules = dict(original(*args, **kwargs))
        diagnostic_status(modules)
        return modules

    monkeypatch.setattr(selfhost_lsp_double, 'modules_for', modules_for)
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('cancel_hints',))
    for op, code, expected in [('pieces', 0, b'bounds:1:3'),
                               ('spread', 41, b'[loop v in items v or_throw<Canceled>]...'),
                               ('coalesce', 41, b'or `??<Canceled>` to default it'),
                               ('replace', 41, b'in place of the whole `??`'),
                               ('parallel', 41, b'body cannot forward it')]:
        outputs = [subprocess.run([b, op], capture_output=True, timeout=60) for b in binaries]
        assert all(r.returncode == code for r in outputs), [(r.returncode, r.stderr) for r in outputs]
        assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
        assert expected in outputs[0].stdout
        if op == 'pieces':
            assert b'raw:x\xff' in outputs[0].stdout
            assert b'long:\nmissing::false' in outputs[0].stdout
