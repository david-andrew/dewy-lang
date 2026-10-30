"""Whole immediate, indexed-memory and relocation functions against frozen Jo."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
code: u8[]
binding = arm64_encoder_bind(&code)
main = ():
    # Every encodable logical mask, every rotation, then arbitrary word patterns.
    loop size in [2, 4, 8, 16, 32, 64]:
        loop ones in [1..size):
            v = (1 << ones) - 1
            loop r in [0..size):
                word = v
                n = size
                loop n < 64:
                    word = word | (word << n)
                    n *= 2
                encoded = a_logimm(word)
                assert(encoded >= 0, "valid logical mask")
                print(encoded)
                v = ((v >> 1) & ((1 << (size - 1)) - 1)) | ((v & 1) << (size - 1))
    x = 1250937
    loop i in [0..2000):
        x = x * 6364136223846793005 + 1442695040888963407
        print(a_logimm(x))
    assert(a_logimm(0) == -1 and a_logimm(-1) == -1, "empty/full mask")
    # Every FP immediate and all exponent alternatives; low-bit rejection.
    loop sign in [0, 1]:
        loop exponent in [0..512):
            loop fraction in [0..16):
                bits = (sign << 63) | (exponent << 54) | (fraction << 48)
                print(a_fimm8(bits, 1))
                assert(a_fimm8(bits | 1, 1) == -1, "double low bits")
        loop exponent in [0..64):
            loop fraction in [0..16):
                bits = (sign << 31) | (exponent << 25) | (fraction << 19)
                print(a_fimm8(bits, 2))
                assert(a_fimm8(bits | 1, 2) == -1, "single low bits")
    loop size in [0, 1, 2, 3, 4, 8, 16]:
        loop sh in [-1, 0, 1, 2, 3, 4]:
            loop load in [false, true]:
                loop signed in [false, true]:
                    loop fp in [false, true]:
                        loop rt in [0, 17, 31]:
                            loop rn in [0, 17, 31]:
                                loop rm in [0, 17, 31]:
                                    code = []
                                    ok = a_mem_idx(load, rt, rn, rm, sh, size, signed, fp)
                                    assert(code.len() == (if ok: 4 else: 0), "reject without emitting")
                                    print(ok)
                                    print(code)
    loop offset in [0, 4, 8]:
        loop base in [0, 4095, 4096, 0x100000000, -4096]:
            loop distance in [-0x100001000, -4097, -4096, -1, 0, 1, 4095, 4096, 0x100001000]:
                code = fill(u8(0), offset)
                w32(0x90000011)
                w32(0x91000231)
                saved = code
                a_patch_adrp(offset, base, base + distance)
                assert(saved[offset] == 17 and saved[offset + 3] == 144, "relocation COW")
                print(code)
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_arm64_field_twins(compiler, tmp_path, release):  # noqa: F811
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
