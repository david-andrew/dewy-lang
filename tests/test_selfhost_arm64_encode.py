"""Whole arm64 encoding functions: frozen bytes and borrowed-buffer lifetime."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
code: u8[]
binding = arm64_encoder_bind(&code)
flush = ():
    print(code)
    code = []

main = ():
    # Read/patch little-endian words, replacement, growth, and COW snapshots.
    w32(0x89ABCDEF)
    assert(rd32(0) == 0x89ABCDEF, "little endian")
    saved = code
    wr32(0, 0x76543210)
    assert(saved == [u8(239), u8(205), u8(171), u8(137)], "patch preserves snapshot")
    assert(rd32(0) == 0x76543210, "patched word")
    loop k in [0..1024): w32(k)
    assert(saved.len() == 4 and rd32(4096) == 1023, "growth keeps header and snapshot")
    growth_snapshot = code
    w32(0xABCDEF)
    wr32(0, 7)
    assert(growth_snapshot.len() == 4100 and code.len() == 4104, "append preserves length snapshot")
    assert(growth_snapshot[0] == 16, "append and patch preserve bytes snapshot")
    flush()
    a_ret()
    assert(rd32(0) == 0xD65F03C0, "ret encoding after replacement")
    a_svc()
    assert(rd32(4) == 0xD4000001, "svc encoding")
    a_bl()
    flush()
    # Every register, including SP/ZR; signed and halfword boundaries.
    loop rd in [0..32):
        loop value in [-9223372036854775807 - 1, -16777216, -65537, -65536, -4096, -4095, -1, 0, 1, 4095, 4096, 65535, 65536, 65537, 0xFFFF0000, 0x1234000056780000, 9223372036854775807]:
            a_mov_imm(rd, value)
            loop hw in [0..4):
                a_movz(rd, value, hw)
                a_movk(rd, value, hw)
                a_movn(rd, value, hw)
            loop rn in [0, 9, 17, 29, 31]:
                a_add_imm(rd, rn, value)
                a_sub_imm(rd, rn, value)
        a_blr(rd)
        a_br(rd)
        loop rn in [0..32):
            a_mov(rd, rn)
            a_cmp(rd, rn)
            a_cmp_imm(rd, rn)
            loop cc in [0..16): a_cset(rd, cc)
            loop rm in [0, 16, 31]:
                loop base in [A_ADD, A_SUB, A_AND, A_ORR, A_EOR, A_SDIV, A_UDIV, A_LSLV, A_LSRV, A_ASRV]:
                    a_rrr(base, rd, rn, rm)
                a_mul(rd, rn, rm)
                a_msub(rd, rn, rm, 31)
                loop sh in [0, 1, 31, 32, 63]: a_add_lsl(rd, rn, rm, sh)
        loop immr in [0..64):
            loop imms in [0..64):
                a_ubfm(rd, 31, immr, imms)
                a_sbfm(rd, 0, immr, imms)
        flush()
    # Scaled, unscaled and synthesized addresses, both float widths and Q regs.
    loop size in [1, 2, 4, 8, 16]:
        loop fp in [false, true]:
            if size == 16 and not fp: continue
            loop load in [false, true]:
                loop signed in [false, true]:
                    loop off in [-65537, -4096, -257, -256, -255, -1, 0, 1, 255, 256, 257, 4095, 4096, 4095 * size, 4096 * size, 65536]:
                        loop rt in [0, 9, 16, 31]:
                            loop rn in [0, 17, 29, 31]:
                                a_mem(load, rt, rn, off, size, signed, fp)
                    flush()
    loop off in [-4096, -1, 0, 8, 32760, 32768]:
        a_ldr(0, 31, off)
        a_str(31, 0, off)
    loop ty in [1, 2]:
        print(fty(ty))
        loop rd in [0..32):
            loop rn in [0..32):
                a_fmov_from(ty, rd, rn)
                a_fmov_to(ty, rd, rn)
                a_fcmp(ty, rd, rn)
                loop base in [AF_ADD, AF_SUB, AF_MUL, AF_DIV]: a_fop(base, ty, rd, rn, 31)
                loop base in [AF_SQRT, AF_NEG, AF_ABS, AF_MOV, AF_FLOOR, AF_CEIL, AF_TRUNC]: a_fun(base, ty, rd, rn)
                loop cc in [0..16): a_fcsel(ty, rd, rn, 0, cc)
            flush()
    # Rebinding writes only the new header, then the original can be rebound.
    second: u8[]
    arm64_encoder_bind(&second)
    a_ret()
    assert(code.len() == 0 and second.len() == 4, "rebinding")
    arm64_encoder_bind(&code)
    a_svc()
    assert(second == [u8(192), u8(3), u8(95), u8(214)], "other buffer preserved")
    flush()
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_arm64_encoding_twins(compiler, tmp_path, release):  # noqa: F811
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
