"""Read/patch views preserve unaligned words, neighboring bytes and COW aliases."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_arm64_word_views(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        leaf = f'arm64_encode.{extension}'
        (directory / leaf).write_text((ROOT / 'compiler' / leaf).read_text())
        source = directory / 'driver.jo'
        source.write_text(f"use '{leaf}'\n" + r'''
code: u8[]
binding = arm64_encoder_bind(&code)
main = ():
    loop offset in [0..13):
        code = fill(u8(165), 16)
        before = code
        wr32(offset, 0xFEDCBA98)
        assert(rd32(offset) == 0xFEDCBA98, "unaligned word")
        assert(before == fill(u8(165), 16), "shared buffer unchanged")
        loop i in [0..16):
            if i < offset or i >= offset + 4: assert(code[i] == 165, "neighbor unchanged")
        after = code
        wr32(offset, -1)
        assert(rd32(offset) == 0xFFFFFFFF, "low word only")
        assert(after[offset] == 152, "repeated COW")
        wr32(offset, 0)
        assert(rd32(offset) == 0, "unique patch")
        print(code)
    code = []
    w32(0x12345678)
    wr32(0, 0x87654321)
    print(rd32(0))
''')
        binary = directory / 'driver'
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
