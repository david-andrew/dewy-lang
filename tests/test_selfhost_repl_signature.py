"""REPL signatures preserve overload documentation and the stored host callback ABI."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'repl_signature.dewy'
use 'host_binds.jo'
use 'check.jo'
use 'checker_state.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'source_types.dewy'
use 'util.jo'
main = ():
    src = "# First line\n# More docs\nshow = (x: int) -> int: x\n# Second doc\nshow = (x: str) -> str: x\n"
    files = [SrcFile(path="case.jo", src=src)]
    nodes = [Node()]; syms = [Sym()]; modules = [Module()]; module_added(0)
    ctxs = [FnCtx(mod=0)]; cx = 0
    nm = intern("show")
    first = mk(.fn_, mkpos(0, find(src, "show"))); nodes[first].name = i32(nm)
    second = mk(.fn_, mkpos(0, rfind(src, "show"))); nodes[second].name = i32(nm)
    scope_add_module(0, nm, .fns, 0, first)
    scope_add_module(0, nm, .fns, 0, second)
    e = mk(.ident, 42); nodes[e].name = i32(nm)
    exprstmt_repl(e)
    print("first:\n{repl_sig}")
    print("node:{nodes[e].kind == .int_lit}:{nodes[e].pos == 42}")
    e = mk(.ident, 43); nodes[e].name = i32(nm); repl_sig = "prefix"
    exprstmt_host.repl(e)
    print("second:\n{repl_sig}")
    e = mk(.ident, 44); nodes[e].name = i32(intern("missing")); old = repl_sig
    exprstmt_repl(e)
    print("missing:{nodes[e].kind == .ident}:{repl_sig == old}")
'''


def test_repl_signature_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('repl_signature',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    for expected in (b'First line', b'    More docs', b'Second doc', b'x: int', b'x: str',
                     b'node:true:true', b'second:\nprefix\n', b'missing:true:true'):
        assert expected in outputs[0].stdout
