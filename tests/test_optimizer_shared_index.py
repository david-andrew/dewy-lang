"""Shared optimizer state obeys the operand ABI and survives SRA mutations."""
from pathlib import Path
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.core_quick
def test_shared_optimizer_index(compiler, tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'shared-index.jo'
    source.write_text(f"use '{root}/compiler/ir_types.dewy'\nuse '{root}/compiler/ir.jo'\nuse '{root}/compiler/opt.jo'\nuse '{root}/compiler/opt_workspace.dewy'\n" + '''
# Rewrite every operand shape, including indexed memory and indirect targets.
loop opcode in [0..int(Op.findb) + 1):
    loop indexed in [0, M_INDEX]:
        ir_begin("rewrite", 0)
        ir.vtypes = fill(i8(VI), 64)
        ir.args = [i32(0), i32(5), i32(6), i32(0)]
        o_resize(64)
        loop v in [0..32): o_regs[v].repl = i32(v + 16)
        op = Op(opcode)
        mode = if op == .load or op == .store: 8 | indexed else: 3
        ins = Ins(op, VI, 4, 1, 2, i32(mode), 0)
        expected: int[]
        defined = ir_operands(ins)
        loop k in [0..ir_use_count): expected.push(ir_use(k) + 16)
        o_rewrite(ins)
        got = ir_operands(ins)
        if got != defined or ir_use_count != expected.len(): print("definition mismatch {opcode}")
        loop k in [0..ir_use_count):
            if ir_use(k) != expected[k]: print("use mismatch {opcode} {indexed} {k}")

# Scalarizing a slot removes address definitions and inserts lane definitions.
# Check the maintained index independently, also after workspace shrink/growth.
loop nv in [16, 2048, 24]:
    ir_begin("sra", 0)
    ir.vtypes = fill(i8(VI), nv)
    ir.slot_size = [i32(16)]
    ir.slot_align = [i32(8)]
    ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0),
               Ins(.iconst, VI, 1, 0, 0, 0, 42),
               Ins(.store, VI, 0, 0, 1, 8, 0),
               Ins(.load, VI, 2, 0, 0, 8, 0),
               Ins(.ret, 0, 0, 2, 0, 0, 0)]
    o_sra()
    expected = fill(0, ir.vtypes.len())
    loop ins in ir.code:
        d = ir_operands(ins)
        if d >= 0: expected[d] += 1
    loop v in [0..expected.len()):
        if o_regs[v].ndef != i32(expected[v]): print("SRA definition mismatch {nv} {v}")
print("shared index ok")
''')
    binary = tmp_path / 'shared-index'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'shared index ok\n', ran.stdout
