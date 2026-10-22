"""Backend workspace reuse must not retain the previous function's locations."""
import subprocess

import pytest

from tests.support import ROOT, compiler


@pytest.mark.core_quick
def test_backend_workspace_reuses_storage_without_locations(compiler, tmp_path):
    source = tmp_path / 'workspace.jo'
    source.write_text(f"use '{ROOT / 'compiler/x64.jo'}'\nuse '{ROOT / 'compiler/ir.jo'}'\n" + '''
ir_begin("large", 0)
loop i in [0..256):
    v = vreg(VI)
    emit(.gaddr, VI, v, 0, 0, 0, 64 + i)
    e_ret(v)
analyze(true)
capacity = v_live_storage.len()
assert(vgkind[0] == 1 and vgoff[0] == 64, "global location")
assert(v_live[0].nuse == 1, "uses")
vsoff[0] = 123
vsave[0] = true
ir_begin("small", 1)
v = vreg(VI)
emit(.slot, VI, v, new_slot(8, 8), 0, 0, 0)
e_ret(v)
analyze(true)
assert(v_live_storage.len() == capacity, "retained capacity")
assert(v_live[0].ndef == 1 and v_live[0].nuse == 1, "fresh uses")
assert(vslot[0] == 0 and vsoff[0] == 0, "fresh slot")
assert(not vsave[0], "fresh saves")
ir_begin("data", 2)
v = vreg(VI)
emit(.daddr, VI, v, 0, 0, 0, 96)
e_ret(v)
analyze(true)
assert(vgkind[0] == 0 and vgoff[0] == 96, "data after global")
ir_begin("empty", 3)
analyze(true)
allocate()
print("ok")
''')
    binary = tmp_path / 'workspace'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'ok\n'
