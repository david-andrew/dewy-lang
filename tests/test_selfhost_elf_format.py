"""ELF64 images: complete frozen bytes, section layouts and borrowed inputs."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
read32 = (bytes: u8[], at: int) -> int:
    int(bytes[at]) | (int(bytes[at + 1]) << 8) | (int(bytes[at + 2]) << 16) | (int(bytes[at + 3]) << 24)

main = ():
    loop machine in [62, 183]:
        elf_machine = machine
        loop page in [4096, 65536]:
            elf_page = page
            loop length in [0, 31, 4097]:
                loop symbols in [false, true]:
                    text = fill(u8(0xCC), length)
                    ro = [u8(0), u8(0x80), u8(0xFF)]
                    text_before = text
                    ro_before = ro
                    elf_syms = []
                    elf_extra = [(".debug_line", [u8(42), u8(0)]), (".note_é", [u8(0xFF)])]
                    if symbols: elf_syms = [("_start", 0, length), ("é_function", 3, 7)]
                    syms_before = elf_syms
                    extra_before = elf_extra
                    image = elf_image(text, 0, ro, 0x12345)
                    assert(text == text_before and ro == ro_before and elf_syms == syms_before and elf_extra == extra_before, "borrowed image inputs")
                    layout = elf_layout(length, ro.len())
                    assert(layout.0 == page and layout.1 % page == 0 and layout.2 % page == 0, "segment alignment")
                    assert(image[0] == 0x7F and image[1] == 'E' and image[2] == 'L' and image[3] == 'F', "ELF magic")
                    assert(read32(image, 24) == ELF_BASE + page and image[18] == u8(machine), "entry and machine")
                    assert(image[layout.1] == 0 and image[layout.1 + 1] == 0x80 and image[layout.1 + 2] == 0xFF, "rodata bytes")
                    print(image)
    bytes: u8[] = [0xAA]
    before = bytes
    put16(bytes, -1)
    put32(bytes, 0x123456789)
    put64(bytes, -9223372036854775807 - 1)
    assert(before == [u8(0xAA)], "word writers retain COW")
    print(bytes)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_elf_format_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        source = tmp_path / f'driver-{extension}.jo'
        binary = tmp_path / f'driver-{extension}'
        source.write_text(f"use '{ROOT}/compiler/elf_format.{extension}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
