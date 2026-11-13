"""Copy forwarding preserves COW inputs and agrees with its frozen twin."""
import shutil
import subprocess

import pytest

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
run = (size: int, raw: bool, extra: bool):
    ir = IrFn(vtypes=fill(i8(VI), 6), slot_size=[i32(size), i32(size), i32(size)],
              args=[i32(1)], raw_mem=raw)
    ir.code = [Ins(.slot, VI, 0, 0), Ins(.slot, VI, 1, 1), Ins(.slot, VI, 2, 2),
               Ins(.copy, a=1, b=0, imm=size), Ins(.copy, a=2, b=1, imm=size),
               Ins(.ret, a=-1)]
    if extra: ir.code.insert(4, Ins(.call, dst=-1, a=0, b=1))
    saved = ir
    o_copy_forward()
    assert(saved.code[3].op == Op.copy and saved.code[4].b == 1, "COW input")
    if not raw and not extra:
        assert(ir.code[3].op == Op.nop and ir.code[4].b == 0, "forwarded pair")
    else:
        assert(ir.code[3].op == Op.copy, "blocked forwarding")
    print("{size} {raw} {extra}")
    loop ins in ir.code: print("{ins.op} {ins.dst} {ins.a} {ins.b} {ins.c} {ins.imm}")

loop size in [1, 2, 4, 8, 16]:
    run(size, false, false)
    run(size, true, false)
    run(size, false, true)
print("ok")
'''


def compare_copy_forward(compiler, tmp_path, release):
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        source_dir = directory / 'compiler'
        shutil.copytree(ROOT / 'compiler', source_dir)
        imports = ''.join(f"use '{source_dir / name}'\n" for name in
                          ('ir_types.dewy', 'ir.jo', 'ir_builders.dewy', 'opt.jo',
                           f'opt_copy_forward.{extension}'))
        source = directory / 'driver.jo'
        binary = directory / 'driver'
        source.write_text(imports + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=15)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith('ok\n')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_opt_copy_forward_twins(compiler, tmp_path, release):  # noqa: F811
    compare_copy_forward(compiler, tmp_path, release)


def test_opt_copy_forward_self_build_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    results = compare_builds(compiler, tmp_path, monkeypatch, ('opt_copy_forward',),
                             ('compiler/main.jo',), flags=(('--release',),))
    assert results[0][2] == 0
