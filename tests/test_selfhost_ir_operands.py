"""Frozen layout twins and exhaustive comparison with the optimizer's operand view."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
main = ():
    modes = ir_operand_layouts()
    assert(modes.len() == int(Op.findb) + 1, "opcode coverage")
    print("{IR_DEF} {IR_ARGS} {IR_INDEX} {IR_STORE} {IR_INDIRECT} {IR_RETURN} {IR_CALL} {IR_NARROW32} {IR_OVERFLOW}")
    ir.args = [i32(19), i32(23), i32(29), i32(31)]
    loop tag in [0..modes.len()):
        print("{tag} {modes[tag]}")
        loop indexed in [0..2):
            loop count in [0..4):
                loop returned in [-1..1):
                    ins = Ins(op=Op(tag), dst=41, a=1, b=i32(count), c=i32(7 | (indexed * M_INDEX)))
                    if ins.op == .ret: ins.a = i32(returned)
                    expected_def = ir_operands(ins)
                    mode = modes[tag]
                    d = -1
                    if mode & IR_DEF != 0: d = int(ins.dst)
                    assert(d == expected_def, "definition")
                    uses: int[]
                    if mode & IR_ARGS != 0:
                        loop i in [0..int(ins.b)): uses.push(int(ir.args[int(ins.a) + i]))
                        if mode & IR_INDIRECT != 0: uses.push(int(ins.c))
                    else:
                        n = mode & 7
                        if mode & IR_RETURN != 0 and ins.a < 0: n = 0
                        if mode & IR_INDEX != 0 and int(ins.c) & M_INDEX != 0: n += 1
                        if mode & IR_STORE != 0:
                            if mode & IR_INDEX == 0: n += 1
                        if n > 0: uses.push(int(ins.a))
                        if n > 1: uses.push(int(ins.b))
                        if n > 2:
                            if mode & IR_STORE != 0: uses.push(int(ins.dst))
                            else: uses.push(int(ins.c))
                    assert(uses.len() == ir_use_count, "use count")
                    loop i in [0..uses.len()): assert(uses[i] == ir_use(i), "ordered use")
    saved = modes
    modes[0] = 99
    fresh = ir_operand_layouts()
    assert(saved[0] == 0 and fresh[0] == 0, "independent tables")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_ir_operand_twins(compiler, tmp_path, release):  # noqa: F811
    # Keep the existing walker independent: it does not read the layout table.
    ir = (ROOT / 'compiler/ir.jo').read_text()
    walker = ir[ir.index('ir_use_count = 0'):ir.index('ir_operand_layout: int[]')]
    outputs = []
    for extension in ('dewy', 'jo'):
        for stem in ('ir_types', 'ir_operands'):
            name = f'{stem}.{extension}'
            text = (ROOT / 'compiler' / name).read_text()
            if extension == 'jo':
                text = text.replace("use 'ir_types.dewy'", "use 'ir_types.jo'")
            (tmp_path / name).write_text(text)
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(f"use 'ir_types.{extension}'\nuse 'ir_operands.{extension}'\n"
                          + 'const M_INDEX = 128\nir: IrFn\n' + walker + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].splitlines()[0] == '8 16 32 64 128 256 512 1024 2048'
    assert outputs[0].endswith('ok\n')
