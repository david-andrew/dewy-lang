"""Loop invariant motion agrees with the frozen Jo pass and preserves inputs."""

import shutil
import subprocess

import pytest

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
ir = IrFn(vtypes=fill(i8(VI), 4), args=[])
code = [Ins(.iconst, dst=0, imm=2), Ins(.iconst, dst=1, imm=3),
        Ins(.block), Ins(.loop), Ins(.mul, dst=2, a=0, b=1),
        Ins(.mul, dst=3, a=0, b=1), Ins(.end), Ins(.end)]
saved = code
out = o_licm(code)
assert(saved[3].op == Op.loop and saved[4].op == Op.mul, "input COW")
assert(out[3].op == Op.mul and out[4].op == Op.mul and out[5].op == Op.loop, "hoisted")
assert(out[3].dst == 2 and out[4].dst == 3, "move order")
loop ins in out: print("{ins.op} {ins.dst} {ins.a} {ins.b} {ins.imm}")
plain = [Ins(.iconst, dst=0, imm=2), Ins(.add, dst=1, a=0, b=0), Ins(.ret, a=1)]
no_move = o_licm(plain)
assert(no_move.len() == 3 and no_move[1].op == Op.add, "no loop")
blocked = [Ins(.iconst, dst=0, imm=2), Ins(.iconst, dst=1, imm=3),
           Ins(.block), Ins(.loop), Ins(.add, dst=0, a=0, b=1),
           Ins(.mul, dst=2, a=0, b=1), Ins(.end), Ins(.end)]
blocked_out = o_licm(blocked)
assert(blocked_out[3].op == Op.loop and blocked_out[5].op == Op.mul, "loop definition blocks hoist")
assert(blocked[3].op == Op.loop and blocked[5].op == Op.mul, "blocked input COW")
loop ins in blocked_out: print("{ins.op} {ins.dst} {ins.a} {ins.b} {ins.imm}")
print("ok")
'''


def compare_licm(compiler, tmp_path, release):
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        source_dir = directory / 'compiler'
        shutil.copytree(ROOT / 'compiler', source_dir)
        imports = ''.join(f"use '{source_dir / name}'\n" for name in
                          ('ir_types.dewy', 'ir.jo', 'ir_builders.dewy', 'opt.jo',
                           f'opt_licm.{extension}'))
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
def test_opt_licm_twins(compiler, tmp_path, release):  # noqa: F811
    compare_licm(compiler, tmp_path, release)


def test_opt_licm_self_build_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    # Self-build reaches LICM even when the small flagship programs do not.
    results = compare_builds(compiler, tmp_path, monkeypatch, ('opt_licm',),
                             ('compiler/main.jo',), flags=(('--release',),))
    assert results[0][2] == 0
