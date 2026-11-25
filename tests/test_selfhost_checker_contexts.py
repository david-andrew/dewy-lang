"""Check incremental module initialization and parent lookup against the frozen checker."""
import subprocess

from tests import selfhost_lsp_double
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly

DRIVER = """use 'main.jo'
use 'check.jo'
use 'checker_contexts.dewy'
use 'checker_state.dewy'
use 'ast.jo'
use 'util.jo'
main = ():
    ctxs = [FnCtx(inst=9, parent=-1), FnCtx(inst=12, parent=0)]
    cx = 1
    print("{ctx_for_inst(12)}:{ctx_for_inst(9)}:{ctx_for_inst(7)}")
    cx = -1
    print(ctx_for_inst(12))
    modules = [Module(is_prelude=true)]
    setup_module_contexts(7)
    d = mk(.int_lit, 0)
    modules.push(Module(name=i32(intern("app")), inits=[d]))
    setup_module_contexts(7)
    setup_module_contexts(7)
    inst = int(modules[1].init_fn)
    b = int(fns[inst].body)
    print("{module_ctx.len()}:{module_frames.len()}:{module_ctx[0]}:{module_ctx[1]}")
    print("{modules[0].init_fn}:{module_frames[0].inst}:{module_frames[1].inst == inst}:{module_frames[1].mod}")
    print("{nodes[b].kind == .block}:{nkids(b)}:{kid(b, 0) == d}")
    saved = ctxs.len()
    first = enter_module_context(1)
    again = enter_module_context(1)
    print("{first}:{again}:{module_ctx[1] == saved}:{ctxs.len() == saved + 1}:{ctxs[saved].inst == inst}")
"""


def test_checker_contexts_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('checker_contexts',)):
        result = subprocess.run([binary], check=True, capture_output=True, timeout=60)
        assert result.stdout == b'1:0:-1\n-1\n2:2:-1:-1\n7:7:true:1\ntrue:1:true\ntrue:false:true:true:true\n'
