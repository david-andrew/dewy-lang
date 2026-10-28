"""PE32+ images: frozen imports, unwind encodings, resources and section tables."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
main = ():
    loop rva in [0x1000, 0x11000, 0x12345000]:
        print(pe_idata(rva))
        print(pe_layout(rva, rva + 1))
    loop size in [0, 8, 32, 128, 136, 4096, 512 * 1024 - 8, 512 * 1024]:
        loop kind in [UW_FRAME, UW_ADAPTER, UW_ENTRY]:
            out: u8[] = [0xAA]
            before = out
            pe_unwind_info(out, kind, size)
            assert(before == [u8(0xAA)], "unwind writer COW")
            print(out)
    # Mixed sorted/unsorted functions and repeated unwind descriptions.
    uw_data = [256, 4, 5, 9, 16, 2, 20, 3, 32, 24, 12, 48]
    unwind_fns = [(80, 120, UW_SAVES, 0), (0, 40, UW_FRAME, 32), (40, 80, UW_FRAME, 32), (120, 180, UW_ADAPTER, 160), (180, 224, UW_ENTRY, 8)]
    before = unwind_fns
    print(pe_unwind(0x4000, 0x1000))
    assert(unwind_fns == before, "unwind sorting keeps source order")
    png = fill(u8(0), 28)
    png[16] = 1
    png[19] = 127
    png[22] = 1
    png[23] = 0
    loop size in [0, 1, 511, 512, 513]:
        loop gui in [false, true]:
            loop debug in [false, true]:
                text = fill(u8(0xCC), size)
                ro: u8[] = [0, 0x80, 0xFF]
                info: u8[] = [1, 2, 3]
                icon: u8[]
                if gui: icon = png
                name = ""
                if debug: name = "prøgram.pdb"
                guid = fill(u8(0x3A), 16)
                text_before = text
                ro_before = ro
                icon_before = icon
                sections_before = pe_section_headers
                image = pe_image(text, 0, ro, 0x12345, gui, info, icon, name, guid)
                assert(image[0] == 'M' and image[1] == 'Z' and image[64] == 'P' and image[65] == 'E', "PE magic")
                assert(text == text_before and ro == ro_before and icon == icon_before and unwind_fns == before, "borrowed image inputs")
                assert(pe_section_headers.len() == (if gui: 6 else: 5) * 40, "section count")
                print(image)
                print(pe_section_headers)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_pe_format_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in ('elf_format', 'pe_format'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(f"use 'pe_format.{extension}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
