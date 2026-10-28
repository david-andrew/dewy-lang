"""Structured branches: signed patch limits, nested destinations and shared state."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
code: u8[]
binding = arm64_encoder_bind(&code)
main = ():
    # Signed imm19 boundaries: reject before writing, including COW snapshots.
    loop kind in [0, 1, 7]:
        loop d in [-33554433, -33554432, -262145, -262144, -1, 0, 1, 262143, 262144, 33554431, 33554432]:
            code = []
            w32(0x5400000B)
            before = code
            ok = a_try_patch((0, kind), d * 4)
            expected = kind == 0 or (d >= -262144 and d < 262144)
            assert(ok == expected, "range status")
            assert(before == [u8(11), u8(0), u8(0), u8(84)], "patch snapshot")
            if not ok: assert(code == before, "rejected patch is unchanged")
            else:
                bits = (d & 0x7FFFF) << 5
                if kind == 0: bits = d & 0x3FFFFFF
                assert(rd32(0) == (0x5400000B | bits), "displacement bits")
            print(code)
    # Nest block/loop/if in every order, targeting every enclosing depth.
    loop outer in [0..3):
        loop inner in [0..3):
            loop depth in [0, 1]:
                loop operand in [0..32):
                    code = []
                    w32(0xD503201F)
                    actl = [ACtl(outer, 0, [], [(0, 1)]), ACtl(inner, 4, [], [])]
                    saved = actl
                    a_branch(depth)
                    a_branch_nz(operand, depth)
                    a_branch_cc(operand & 15, depth)
                    c = 1 - depth
                    assert(saved[c].fixups.len() == 0, "control snapshot")
                    assert(actl[0].ifx == [(0, 1)], "if fixups preserved")
                    assert(actl[depth].fixups.len() == 0, "other control unchanged")
                    if actl[c].kind == 1:
                        assert(actl[c].fixups.len() == 0, "loop has no pending branches")
                        loop j in [0..3):
                            site = 4 + 4 * j
                            d = (actl[c].start - site) / 4
                            expected = 0x14000000 | (d & 0x3FFFFFF)
                            if j == 1: expected = 0xB5000000 | ((d & 0x7FFFF) << 5) | operand
                            if j == 2: expected = 0x54000000 | ((d & 0x7FFFF) << 5) | (operand & 15)
                            assert(rd32(site) == expected, "back edge")
                    else:
                        assert(actl[c].fixups == [(4, 0), (8, 1), (12, 1)], "stable fixup order")
                        loop f in actl[c].fixups:
                            assert(a_try_patch(f, code.len()), "forward patch")
                        assert(rd32(4) == 0x14000003, "forward B")
                        assert(rd32(8) == (0xB5000040 | operand), "forward CBNZ")
                        assert(rd32(12) == (0x54000020 | (operand & 15)), "forward condition")
                    print(code)
                    actl = []
                    assert(saved.len() == 2, "function reset preserves snapshot")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_arm64_branch_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        leaf = f'arm64_encode.{extension}'
        (directory / leaf).write_text((ROOT / 'compiler' / leaf).read_text())
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(f"use '{leaf}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
