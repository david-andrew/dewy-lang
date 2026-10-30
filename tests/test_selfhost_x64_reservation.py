"""Complete register encodings preserve prefixes, byte truncation and COW."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_register_encoding_reservation(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        leaf = f'x64_encode.{extension}'
        (directory / leaf).write_text((ROOT / 'compiler' / leaf).read_text())
        source = directory / 'driver.jo'
        binary = directory / 'driver'
        source.write_text(f"use '{leaf}'\n" + r'''
code: u8[]
fixups: (int, int, int)[]
binding = x64_encoder_bind(&code, &fixups)
main = ():
    loop w in [false, true]:
        loop reg in [0..16):
            loop rm in [0..16):
                loop ix in [-1, 0, 7, 8, 15]:
                    loop opc in [-1, 0, 0x89, 0xFF, 0x123]:
                        code = [u8(0xCC)]
                        saved = code
                        use_index(ix, 0)
                        op_rr(opc, w, reg, rm)
                        rexbyte = 0x40
                        if w: rexbyte |= 8
                        if reg & 8 != 0: rexbyte |= 4
                        if ix >= 0 and ix & 8 != 0: rexbyte |= 2
                        if rm & 8 != 0: rexbyte |= 1
                        expected = [u8(0xCC)]
                        if rexbyte != 0x40: expected.push(u8(rexbyte))
                        expected.push(u8(opc & 255))
                        expected.push(u8(0xC0 | ((reg & 7) << 3) | (rm & 7)))
                        assert(code == expected, "prefix and operand bytes")
                        assert(saved == [u8(0xCC)] and fixups.len() == 0, "COW and no relocation")
                        print(code)
    print("ok")
''')
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=45)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
