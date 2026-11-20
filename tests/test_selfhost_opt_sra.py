"""Scalar replacement agrees with its frozen Jo twin: lanes, kinds, escapes and rewrites."""

import shutil
import subprocess

import pytest

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
from tools.compiler.speed_equivalent import freeze


DRIVER = r'''
setup = (name: str, nv: int, sizes: i32[]):
    ir_begin(name, 0)
    ir.vtypes = fill(i8(VI), nv)
    ir.slot_size = sizes
    ir.slot_align = fill(i32(8), sizes.len())
    ir.args = []

typed = (v: int, ty: int): ir.vtypes[v] = i8(ty)

run = ():
    o_sra()
    print("nested {sra_nested} defs {o_regs[0].ndef}")
    dump_ir()

# Integer record lanes, read back through a constant-offset alias.
loop nv in [12, 300, 12]:
    setup("int_record", nv, [i32(16)])
    ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0), Ins(.iconst, VI, 1, 0, 0, 0, 8),
               Ins(.add, VI, 2, 0, 1, 0, 0), Ins(.iconst, VI, 3, 0, 0, 0, 5),
               Ins(.store, VI, 0, 0, 3, 8, 0), Ins(.store, VI, 0, 2, 3, 8, 0),
               Ins(.load, VI, 4, 0, 0, 8, 8), Ins(.load, VI, 5, 2, 0, 8, 0),
               Ins(.add, VI, 6, 4, 5, 0, 0), Ins(.ret, 0, 0, 6, 0, 0, 0)]
    run()

# f32 lanes with vector arithmetic: splat and lane operands, a memory destination.
setup("float_lanes", 24, [i32(16), i32(16)])
loop v in [3..12): typed(v, VS)
ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0), Ins(.slot, VI, 1, 1, 0, 0, 0), Ins(.fconst, VS, 3, 0, 0, 0, 0)]
loop i in [0..4): ir.code.push(Ins(.store, VS, 0, 0, 3, i32(4 | M_FLOAT), 4 * i))
ir.code.push(Ins(.vop, 0, 0, 1, 0, 3, 2 | (4 << 4) | VOP_SPLAT_C))
ir.code.push(Ins(.vop, 0, 0, 2, 1, 0, 0 | (4 << 4)))
ir.code.push(Ins(.vop, 0, 0, 1, 3, 1, 1 | (4 << 4) | VOP_SPLAT_B))
ir.code.push(Ins(.vop, 0, 0, 0, 1, 0, 3 | (4 << 4)))
ir.code.push(Ins(.load, VS, 4, 1, 0, i32(4 | M_FLOAT), 12))
ir.code.push(Ins(.load, VS, 5, 0, 0, i32(4 | M_FLOAT), 4))
ir.code.push(Ins(.ret, 0, 0, 4, 0, 0, 0))
run()

# One- and two-byte slots: zero and sign extension; a mixed-width slot narrows to 4.
setup("narrow", 16, [i32(1), i32(2), i32(8)])
ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0), Ins(.slot, VI, 1, 1, 0, 0, 0), Ins(.slot, VI, 2, 2, 0, 0, 0),
           Ins(.iconst, VI, 3, 0, 0, 0, -3),
           Ins(.store, VI, 0, 0, 3, 1, 0), Ins(.store, VI, 0, 1, 3, 2, 0),
           Ins(.store, VI, 0, 2, 3, 4, 0), Ins(.store, VI, 0, 2, 3, 4, 4),
           Ins(.load, VI, 4, 0, 0, i32(1 | M_SIGNED), 0), Ins(.load, VI, 5, 1, 0, 2, 0),
           Ins(.load, VI, 6, 2, 0, i32(4 | M_SIGNED), 4), Ins(.load, VI, 7, 2, 0, 4, 0),
           Ins(.ret, 0, 0, 6, 0, 0, 0)]
run()

# Copies: slot to slot, slot to memory and memory to slot; zero and zeroslots.
setup("copies", 24, [i32(16), i32(16), i32(16), i32(8)])
ir.args = [i32(0), i32(6), i32(7)]
ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0), Ins(.slot, VI, 1, 1, 0, 0, 0), Ins(.slot, VI, 2, 2, 0, 0, 0),
           Ins(.slot, VI, 3, 3, 0, 0, 0), Ins(.zeroslots, 0, 0, 0, 3, 0, 0),
           Ins(.iconst, VI, 4, 0, 0, 0, 9), Ins(.store, VI, 0, 0, 4, 8, 0),
           Ins(.copy, 0, 0, 1, 0, 0, 16), Ins(.copy, 0, 0, 5, 1, 0, 16),
           Ins(.copy, 0, 0, 2, 5, 0, 16), Ins(.zero, 0, 0, 3, 0, 0, 8),
           Ins(.load, VI, 8, 2, 0, 8, 8), Ins(.load, VI, 9, 3, 0, 8, 0),
           Ins(.ret, 0, 0, 8, 0, 0, 0)]
run()

# Copy endpoints of different lane widths keep the wider one in memory; float
# and integer classes that reach memory leave too.
setup("copy_kinds", 24, [i32(16), i32(12), i32(16), i32(16)])
loop v in [10..14): typed(v, VS)
typed(14, VF)
ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0), Ins(.slot, VI, 1, 1, 0, 0, 0), Ins(.slot, VI, 2, 2, 0, 0, 0),
           Ins(.slot, VI, 3, 3, 0, 0, 0), Ins(.fconst, VS, 10, 0, 0, 0, 0), Ins(.fconst, VF, 14, 0, 0, 0, 0),
           Ins(.store, VS, 0, 1, 10, i32(4 | M_FLOAT), 0), Ins(.copy, 0, 0, 0, 1, 0, 12),
           Ins(.store, VF, 0, 2, 14, i32(8 | M_FLOAT), 0), Ins(.iconst, VI, 4, 0, 0, 0, 1),
           Ins(.store, VI, 0, 3, 4, 8, 0), Ins(.copy, 0, 0, 3, 2, 0, 16),
           Ins(.copy, 0, 0, 5, 3, 0, 16), Ins(.load, VI, 6, 0, 0, 8, 0),
           Ins(.ret, 0, 0, 6, 0, 0, 0)]
run()

# Escapes: calls, indirect targets, indexed access, returns and unknown uses;
# a slot address stored into another slot asks for a nested retry.
setup("escapes", 24, [i32(8), i32(8), i32(8), i32(8), i32(8), i32(40), i32(8)])
ir.args = [i32(0)]
ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0), Ins(.slot, VI, 1, 1, 0, 0, 0), Ins(.slot, VI, 2, 2, 0, 0, 0),
           Ins(.slot, VI, 3, 3, 0, 0, 0), Ins(.slot, VI, 4, 4, 0, 0, 0), Ins(.slot, VI, 5, 5, 0, 0, 0),
           Ins(.slot, VI, 6, 6, 0, 0, 0),
           Ins(.call, VI, 7, 0, 1, 0, 3), Ins(.calli, VI, 8, 0, 0, 1, 0),
           Ins(.iconst, VI, 9, 0, 0, 0, 2), Ins(.load, VI, 10, 2, 9, i32(8 | M_INDEX), 0),
           Ins(.store, VI, 0, 6, 3, 8, 0), Ins(.load, VI, 11, 6, 0, 8, 0),
           Ins(.add, VI, 12, 4, 4, 0, 0), Ins(.load, VI, 13, 5, 0, 8, 0),
           Ins(.ret, 0, 0, 3, 0, 0, 0)]
run()

# Forward and redefined address chains stay in memory.
setup("chains", 16, [i32(16), i32(16)])
ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0), Ins(.add, VI, 2, 0, 1, 0, 0), Ins(.iconst, VI, 1, 0, 0, 0, 8),
           Ins(.slot, VI, 3, 1, 0, 0, 0), Ins(.mov, VI, 4, 3, 0, 0, 0), Ins(.mov, VI, 4, 4, 0, 0, 0),
           Ins(.load, VI, 5, 2, 0, 8, 0), Ins(.load, VI, 6, 4, 0, 8, 0),
           Ins(.ret, 0, 0, 5, 0, 0, 0)]
run()

# Unaligned and out-of-range accesses keep the slot in memory.
setup("unaligned", 12, [i32(16), i32(16), i32(24)])
ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0), Ins(.slot, VI, 1, 1, 0, 0, 0), Ins(.slot, VI, 2, 2, 0, 0, 0),
           Ins(.load, VI, 3, 0, 0, 8, 4), Ins(.load, VI, 4, 1, 0, 8, 16), Ins(.load, VI, 5, 2, 0, 8, 16),
           Ins(.ret, 0, 0, 5, 0, 0, 0)]
run()
setup("no_slots", 4, [])
ir.code = [Ins(.iconst, VI, 0, 0, 0, 0, 1), Ins(.ret, 0, 0, 0, 0, 0, 0)]
run()
print("ok")
'''


def compare_sra(compiler, tmp_path, release):
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        source_dir = directory / 'compiler'
        shutil.copytree(ROOT / 'compiler', source_dir)
        if extension == 'jo':
            freeze(source_dir, ('opt_sra',))
        imports = ''.join(f"use '{source_dir / name}'\n" for name in
                          ('ir_types.dewy', 'ir.jo', 'ir_builders.dewy', 'opt_workspace.dewy',
                           'opt.jo', f'opt_sra.{extension}'))
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
    return outputs[0]


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_opt_sra_twins(compiler, tmp_path, release):  # noqa: F811
    out = compare_sra(compiler, tmp_path, release)
    functions = out.split('fn ')[1:]
    assert len(functions) == 11, out
    # The plain record and the float lanes leave memory entirely.
    for body in functions[:4]:
        assert 'slot a=' not in body and 'load a=' not in body, body
    assert 'nested true' in out


def test_opt_sra_self_build_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    # The self-build runs SRA on every compiler function.
    results = compare_builds(compiler, tmp_path, monkeypatch, ('opt_sra',),
                             ('compiler/main.jo',))
    assert results[0][2] == 0
