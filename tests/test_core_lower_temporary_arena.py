"""Statement cleanup keeps nested marks correct after an enclosing early release."""
import subprocess

import pytest

from tests.support import ROOT, compiler


@pytest.mark.core_quick
def test_lower_temporary_arena_nested_early_release(compiler, tmp_path):
    source = tmp_path / 'temporary_arena.jo'
    source.write_text(''.join(f"use '{ROOT / 'compiler' / (name + '.jo')}'\n"
                              for name in ('lower', 'ir', 'types')) + '''
init_types()
ir_begin("temps", 0)
loop round in [0..3):
    stmt_begin()
    parent = TempItem(true, new_slot(8, 8), T_INT, false)
    tl_values.push(parent)
    stmt_begin()
    inner_slot = new_slot(8, 8)
    tl_values.push(TempItem(true, inner_slot, T_INT, true))
    assert(tl_items[1] == 1, "nested mark")
    arg_snapshots.push(parent)
    release_arg_snapshots(0)
    assert(tl_values.len() == 1 and tl_items[1] == 0, "shifted nested mark")
    marker = tl_nop[1]
    stmt_end()
    assert(tl_items.len() == 1 and tl_values.len() == 0, "nested cleanup")
    zero = ir.code[marker]
    assert(zero.op == .zeroslots and zero.b == 1, "conditional zero inventory")
    assert(ir.args[int(zero.a)] == i32(inner_slot * 2), "zero slot identity")
    stmt_end()
    assert(tl_items.len() == 0 and tl_values.len() == 0, "empty arena")
print("ok")
''')
    binary = tmp_path / 'temporary_arena'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'ok\n'
