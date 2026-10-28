"""Mach-O images and watch loader: frozen bytes, signatures and source snapshots."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
code: u8[]
binding = arm64_encoder_bind(&code)
main = ():
    imports = [(0, "/usr/lib/libSystem.B.dylib", "munmap"), (8, "/usr/lib/libSystem.B.dylib", "mmap"), (16, "/usr/lib/libSystem.B.dylib", "pthread_jit_write_protect_np"), (24, "@rpath/optional.dylib", "probe"), (32, "/System/Library/Frameworks/F.framework/F", "name")]
    elf_syms = [("main", 0, 4), ("é_function", 4, 16)]
    syms_before = elf_syms
    before = imports
    loop size in [4, 4097]:
        loop watch in [false, true]:
            loop debug in [false, true]:
                loop bundle in [false, true]:
                    text = fill(u8(0xAA), size)
                    ro: u8[] = [0, 0x80, 0xFF]
                    info: u8[] = [1, 2, 3]
                    macho_plist = []
                    macho_resources = []
                    if bundle:
                        macho_plist = [u8(1), u8(2)]
                        macho_resources = [u8(3), u8(4)]
                    macho_dwarf = []
                    if debug: macho_dwarf = [(".debug_info", [u8(0x81), u8(2)]), (".debug_line", [u8(0)])]
                    text_before = text
                    dwarf_before = macho_dwarf
                    image = macho_image(text, 0, ro, info, 0x12345, "prøgram", watch, imports)
                    assert(macho_error == "" and image[0] == 0xCF and image[1] == 0xFA and image[2] == 0xED and image[3] == 0xFE, "Mach-O magic")
                    assert(text == text_before and elf_syms == syms_before and macho_dwarf == dwarf_before and imports == before, "borrowed image metadata")
                    layout = macho_layout(text.len(), ro.len(), info.len())
                    assert(image[layout.0] == 0xAA and image[layout.1 + 1] == 0x80, "text and rodata")
                    print(image)
    image = macho_image([], 0, [], [], 0x30000000, "huge", true, imports)
    assert(image.len() == 0 and macho_error != "", "watch region rejected")
    print(macho_error)
    macho_dwarf = []
    macho_plist = []
    macho_resources = []
    print(macho_image([], 0, [], [], 0, "empty", false, []))
    assert(macho_error == "", "image error reset")
    # The size-only loader and real loader have fixed instruction counts.
    size = 0
    loop address in [0, 0x100004000, 0x123456789000]:
        code = [u8(42), u8(0), u8(0xFF)]
        saved = code
        loader = macho_emit_watch_loader(address, address + 0x4000, 8192, 64, imports, 128)
        assert(macho_error == "" and code == saved and saved == [u8(42), u8(0), u8(0xFF)], "loader restores shared code")
        if address == 0: size = loader.len()
        else: assert(loader.len() == size, "loader address-independent size")
        print(loader)
    saved = code
    loader = macho_emit_watch_loader(1, 2, 8, 0, [], 0)
    assert(loader.len() == 0 and code == saved and macho_error == "dewy-core watch on macOS: the program does not use munmap", "first missing loader import")
    print(macho_error)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_macho_format_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('elf_format', 'leb128', 'sha', 'arm64_encode', 'macho_format')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
