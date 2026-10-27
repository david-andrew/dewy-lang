"""Function literal pools: stable first-use order, bit identity, patches and reset."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
code: u8[]
binding = arm64_encoder_bind(&code)
main = ():
    # Empty calls must neither pad nor modify existing bytes.
    code = [u8(165)]
    a_put_lits()
    assert(code == [u8(165)], "empty pool")
    loop prefix in [0, 4, 8, 12]:
        loop count in [1, 2, 3, 16, 257]:
            code = fill(u8(165), prefix)
            # Signed zero, infinities, NaN payloads and single-precision bits
            # are keys by raw bits, never floating-point equality.
            bits = [0, -9223372036854775808, 0x7FF0000000000000, 0x7FF8000000000001, 0x7FF8000000000002, 0x3F800000, -1]
            loop i in [0..count):
                a_lits.push((code.len(), bits[i % bits.len()]))
                w32(0x58000000 | (i % 32))
            before = code
            pending = a_lits
            pool = (code.len() + 7) & -8
            a_put_lits()
            unique = min(count, bits.len())
            assert(code.len() == pool + unique * 8, "one word per distinct bit pattern")
            assert(a_lits.len() == 0 and pending.len() == count, "reset preserves snapshot")
            loop i in [0..prefix): assert(code[i] == 165, "prefix")
            if pool > before.len(): assert(rd32(before.len()) == 0xD503201F, "alignment nop")
            loop i in [0..count):
                site = prefix + i * 4
                target = pool + (i % bits.len()) * 8
                assert(rd32(site) == (0x58000000 | (i % 32) | (((target - site) / 4) << 5)), "load patch")
                assert(before[site + 1] == 0, "output snapshot")
            loop i in [0..unique):
                assert(rd32(pool + i * 8) == (bits[i] & 0xFFFFFFFF), "low bits")
                assert(rd32(pool + i * 8 + 4) == ((bits[i] >> 32) & 0xFFFFFFFF), "high bits")
            saved = code
            a_put_lits()
            assert(code == saved, "second flush is empty")
            print(code)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_arm64_literal_twins(compiler, tmp_path, release):  # noqa: F811
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
