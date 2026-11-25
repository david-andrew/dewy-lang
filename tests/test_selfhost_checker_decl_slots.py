"""Declaration lookup memoizes a slot and local collision mode grows the arena only on demand."""
import subprocess

from tests import selfhost_lsp_double
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly

DRIVER = """use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'checker_decl_slots.dewy'
use 'check.jo'
use 'checker_state.dewy'
main = ():
    nodes = [Node()]
    d = mk(.fn_, 7)
    before = decl_info(d)
    print("{decl_info(d) == before}:{nodes[d].sym == i32(before)}")
    locals = [Local()]
    collide_locals = false
    collide_local(6)
    print(locals.len())
    collide_locals = true
    collide_local(6)
    collide_local(3)
    print(locals.len())
"""


def test_checker_decl_slots_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('checker_decl_slots',)):
        result = subprocess.run([binary], check=True, capture_output=True, timeout=60)
        assert result.stdout == b'true:true\n1\n6\n'
