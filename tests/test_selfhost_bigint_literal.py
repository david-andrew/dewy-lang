"""Bigint AST construction agrees on signs, limb boundaries and unsigned bits."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'bigint_literal.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'type_ops.dewy'
use 'types.jo'
show = (value: int, unsigned: bool):
    nodes = [Node()]
    n = mk(.int_lit, 7); nodes[n].ival = value
    if unsigned: add_flag(n, NF_U64)
    dewy_coerce_bigint_literal(n, T_INT)
    sign = kid(n, 0); limbs = kid(n, 1)
    print("case:{value}:{unsigned}:{nodes[n].kind == .call}:{nodes[n].pos}:{nodes[n].type == i32(T_INT)}:{has_flag(n, NF_CHECKED)}:{nodes[sign].ival}:{nkids(limbs)}")
    loop item in kids(limbs): print("limb:{nodes[item].ival}:{nodes[item].type == i32(T_U64)}:{has_flag(item, NF_CHECKED)}")
main = ():
    init_types()
    loop value in [0, 1, -1, 4294967296, -4294967296, -9223372036854775807 - 1]: show(value, false)
    show(-1, true)
    show(-9223372036854775807 - 1, true)
'''


def test_bigint_literal_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('bigint_literal',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    for expected in (b'case:0:false:true:7:true:true:0:0',
                     b'case:-4294967296:false:true:7:true:true:-1:2',
                     b'case:-9223372036854775808:false:true:7:true:true:-1:2',
                     b'case:-1:true:true:7:true:true:1:2',
                     b'limb:4294967295:true:true', b'limb:2147483648:true:true'):
        assert expected in outputs[0].stdout
