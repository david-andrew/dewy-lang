"""Versioned loop guards and copies agree with the frozen Jo implementation."""

import shutil
import subprocess

import pytest

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
ir = IrFn(vtypes=fill(i8(VI), 16), args=[])
code = [Ins(.loop), Ins(.add, dst=2, a=0, b=1), Ins(.nop), Ins(.end)]
original = code
L = CLoop(0, 3, 9, 10, 3, false)
out: Ins[]
made = lx_mat(code, L, 2, out)
assert(made >= 16 and out.len() == 1 and out[0].op == Op.add, "invariant rematerialized")
total = lx_sum(code, L, [3], 0, out)
assert(total > made and out.len() == 3 and out[2].op == Op.add, "affine sum")
(lo, hi) = lx_endpoint(code, L, 0, [3, -3], 1, out)
assert(lo >= 0 and hi >= 0 and out.len() > 3, "signed endpoint")
assert(original[1].dst == 2 and original[1].a == 0, "input COW")

input = [Ins(.loop), Ins(.if_, a=3), Ins(.call, c=1), Ins(.end),
         Ins(.br, imm=1), Ins(.end)]
checks = [LCheck(1, 3, -1, 0, 0, 0, 0, [])]
copied: Ins[]
lx_copy(input, 0, 5, checks, [], copied, 2)
assert(copied.len() == 3 and copied[0].op == Op.loop and copied[1].op == Op.br and copied[1].imm == 3 and copied[2].op == Op.end, "guard stripped and branch retargeted")
assert(input[4].imm == 1, "copy preserves source")
print("{made} {total} {lo} {hi} {out.len()} {copied[1].imm} ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_loops_emit_direct_twins(compiler, tmp_path, monkeypatch, release):  # noqa: F811
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        source_dir = directory / 'compiler'
        shutil.copytree(ROOT / 'compiler', source_dir)
        if extension == 'jo':
            path = source_dir / 'loops.jo'
            path.write_text(path.read_text().replace("'loops_emit.dewy'", "'loops_emit.jo'"))
            path = source_dir / 'loops_vector_emit.dewy'
            path.write_text(path.read_text().replace('"loops_emit.dewy"', '"loops_emit.jo"'))
        source = directory / 'driver.jo'
        binary = directory / 'driver'
        imports = ''.join(f"use '{source_dir / name}'\n" for name in
                          ('ir_types.dewy', 'ir.jo', 'loops.jo', f'loops_emit.{extension}'))
        source.write_text(imports + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=20)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith('ok\n')


def test_loops_emit_compiler_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    results = compare_builds(
        compiler, tmp_path, monkeypatch, ('loops_emit',),
        ('tests/ladder/96_ct_crypto/design.dewy',
         'tests/ladder/100_rtos_kernel/design.dewy',
         'tests/ladder/101_ml_training/core.dewy',
         'tests/cases/product_bounds/row_major.dewy',
         'compiler/main.jo'),
        flags=((), ('--release',)),
    )
    assert all(result[2] == 0 for result in results)
