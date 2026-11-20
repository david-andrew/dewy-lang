"""Optimizer opcode tables and entry agree with their frozen Jo twin."""

import shutil
import subprocess

import pytest

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
from tools.compiler.speed_equivalent import freeze


DRIVER = r'''
# Every opcode's decode word, classifiers and simplification kind, under both
# checked-arithmetic policies.
loop k in [0..int(Op.findb) + 1):
    op = Op(k)
    print("{k} {o_decode[k]} {o_simplify_kind(op)} {cse_arity_classify(op, 0)} {cse_arity_classify(op, M_INDEX)} {o_rewrite_mask(op)} {o_control_kind(op)}")
checked_flags = false
wasm = o_make_decode()
loop k in [0..wasm.len()):
    if wasm[k] != o_decode[k]: print("policy {k} {wasm[k]}")
checked_flags = true
print("table {o_make_decode().len()}")

# The entry's register table (reset in Jo): growth, reuse and an entry past the end.
o_resize(3)
o_regs[1].ndef = 5
o_regs[2].repl = 0
o_regs[2].nuse = 7
o_resize_one(40)
o_resize(2)
loop v in [0..41): print("{v} {o_regs[v].ndef} {o_regs[v].repl} {o_regs[v].defpos} {o_regs[v].first} {o_regs[v].nuse} {o_regs[v].dop}")
print("count {o_reg_count} {o_fact_scope.len()} {o_fact_nbr.len()}")

setup = (name: str, nv: int, sizes: i32[]):
    ir_begin(name, 0)
    ir.nparams = 2
    ir.vtypes = fill(i8(VI), nv)
    ir.slot_size = sizes
    ir.slot_align = fill(i32(8), sizes.len())
    ir.args = []

# The entry: SRA then the rewrite group, folding through replaced lanes.
setup("fold", 12, [i32(16)])
ir.code = [Ins(.slot, VI, 2, 0, 0, 0, 0), Ins(.iconst, VI, 3, 0, 0, 0, 5),
           Ins(.store, VI, 0, 2, 3, 8, 0), Ins(.store, VI, 0, 2, 0, 8, 8),
           Ins(.load, VI, 4, 2, 0, 8, 0), Ins(.load, VI, 5, 2, 0, 8, 8),
           Ins(.add, VI, 6, 4, 5, 0, 0), Ins(.mul, VI, 7, 6, 4, 0, 0),
           Ins(.ret, 0, 0, 7, 0, 0, 0)]
optimize()
dump_ir()

# A slot address stored into another slot: the bounded retry runs once.
setup("nested", 12, [i32(8), i32(8)])
ir.code = [Ins(.slot, VI, 2, 0, 0, 0, 0), Ins(.slot, VI, 3, 1, 0, 0, 0),
           Ins(.store, VI, 0, 3, 0, 8, 0), Ins(.store, VI, 0, 2, 3, 8, 0),
           Ins(.load, VI, 4, 2, 0, 8, 0), Ins(.load, VI, 5, 4, 0, 8, 0),
           Ins(.ret, 0, 0, 5, 0, 0, 0)]
optimize()
dump_ir()
print("retry {sra_retry}")

# Structured control and a loop with a dead definition and a constant branch.
setup("control", 12, [])
ir.code = [Ins(.iconst, VI, 2, 0, 0, 0, 0), Ins(.block), Ins(.loop),
           Ins(.add, VI, 2, 2, 1, 0, 0), Ins(.lts, VI, 3, 2, 0, 0, 0),
           Ins(.iconst, VI, 4, 0, 0, 0, 9), Ins(.brif, 0, 0, 3, 0, 0, 0),
           Ins(.end), Ins(.end), Ins(.ret, 0, 0, 2, 0, 0, 0)]
optimize()
dump_ir()
print("ok")
'''


def compare_core(compiler, tmp_path, release):
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        source_dir = directory / 'compiler'
        shutil.copytree(ROOT / 'compiler', source_dir)
        if extension == 'jo':
            freeze(source_dir, ('opt_core',))
        imports = ''.join(f"use '{source_dir / name}'\n" for name in
                          ('ir_types.dewy', 'ir.jo', 'ir_builders.dewy', 'opt_workspace.dewy',
                           'opt.jo', 'opt_sra.dewy', f'opt_core.{extension}'))
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
def test_opt_core_twins(compiler, tmp_path, release):  # noqa: F811
    out = compare_core(compiler, tmp_path, release)
    assert 'table 107' in out and 'policy ' in out
    assert out.count('fn ') == 3 and 'retry false' in out


def test_opt_core_self_build_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    # The self-build decodes and optimizes every compiler function, with release
    # inlining and loop passes on top.
    results = compare_builds(compiler, tmp_path, monkeypatch, ('opt_core',),
                             ('compiler/main.jo',), flags=((), ('--release',)))
    assert results[0][2] == 0 and results[1][2] == 0
