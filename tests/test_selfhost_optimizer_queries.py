"""Optimizer boolean-op classification agrees across every opcode."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'optimizer_queries.dewy'
use 'ir_types.dewy'
use 'ir.jo'
main = ():
    count = 0
    loop i in [0..int(Op.findb) + 1):
        op = i as Op
        if o_boolean_op(op): count += 1
        print("op:{i}:{o_boolean_op(op)}")
    print("booleans:{count}")
'''


def test_optimizer_queries_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('optimizer_queries',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert b'booleans:10' in outputs[0].stdout
