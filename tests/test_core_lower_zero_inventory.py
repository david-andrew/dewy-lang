"""Deferred cleanup preserves entry order when nested statements share a boundary."""
import subprocess

import pytest

from tests.support import ROOT, compiler


@pytest.mark.core_quick
def test_nested_zero_inventory_order(compiler, tmp_path):
    source = tmp_path / 'zero_inventory.jo'
    source.write_text(''.join(f"use '{ROOT / 'compiler' / (name + '.jo')}'\n"
                              for name in ('lower', 'ir', 'types')) + '''
init_types()
loop round in [0..3):
    begin_fn("zeros", 0)
    stmt_begin()
    outer = new_slot(8, 8)
    tl_values.push(TempItem(true, outer, T_INT, true))
    stmt_begin()
    inner = new_slot(8, 8)
    tl_values.push(TempItem(true, inner, T_INT, true))
    stmt_end()
    stmt_end()
    lower_finish()
    assert(ir.code[0].op == .zeroslots and ir.code[1].op == .zeroslots)
    assert(ir.args[int(ir.code[0].a)] == i32(outer * 2), "outer entry first")
    assert(ir.args[int(ir.code[1].a)] == i32(inner * 2), "inner entry second")
    loop ins in ir.code: assert(ins.op != .nop)
    begin_fn("plain", 0)
    stmt_begin()
    e_ret(-1)
    stmt_end()
    lower_finish()
    assert(ir.code.len() == 1 and ir.code[0].op == .ret, "no cleanup marker")
print("ok")
''')
    binary = tmp_path / 'zero_inventory'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'ok\n'
