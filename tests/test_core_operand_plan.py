"""Compare final-IR use plans with the independent optimizer operand view."""
import subprocess

import pytest

from tests.support import ROOT, compiler


@pytest.mark.core_quick
def test_backend_operand_layouts_match_optimizer(compiler, tmp_path):
    source = tmp_path / 'operands.jo'
    source.write_text(f"use '{ROOT / 'compiler/x64.jo'}'\nuse '{ROOT / 'compiler/ir.jo'}'\n" + '''
loop tag in [0..int(Op.findb) + 1):
    loop indexed in [0..2):
        op = Op(tag)
        ir_begin("operands", 0)
        loop v in [0..256): vreg(VI)
        ir.args = [i32(3), i32(4), i32(5), i32(6)]
        if op == .end: e_block()
        if op == .else_: e_if(0)
        a = 0
        if op == .ret and indexed == 0: a = -1
        emit(op, VI, 6, a, 2, 3 | (indexed * M_INDEX), 0)
        if op == .block or op == .loop or op == .if_ or op == .else_: e_end()
        uses = fill(0, 256)
        defs = fill(0, 256)
        loop ins in ir.code:
            d = ir_operands(ins)
            if d >= 0: defs[d] += 1
            loop i in [0..ir_use_count): uses[ir_use(i)] += 1
            if ins.op == .zeroslots:
                loop i in [0..int(ins.b)):
                    item = int(ir.args[int(ins.a) + i])
                    if item & 1 != 0: defs[item >> 1] += 2
        analyze()
        loop v in [0..256):
            assert(v_live[v].nuse == uses[v], "use layout")
            assert(v_live[v].ndef == defs[v], "definition layout")
print("ok")
''')
    binary = tmp_path / 'operands'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'ok\n'
