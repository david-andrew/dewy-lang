"""MSF/PDB and CodeView against frozen bytes and growing debug metadata."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_dwarf_format import SETUP

DRIVER = SETUP + r'''
main = ():
    loop debug in [false, true]:
        reset()
        if not debug: dbg_raw = []
        before = line_rows
        metadata = dbg_raw
        old_types = types
        text = fill(u8(0xCC), 64)
        guid = pdb_guid(text)
        image = pdb_image(guid, 64, fill(u8(0), 200), "src/prøgram.dewy", "test", "/build")
        assert(image.len() % PDB_BLOCK == 0 and image[0] == 'M' and image[1] == 'i', "MSF blocks")
        assert(line_rows == before and dbg_raw == metadata and old_types.len() == 24, "debug source snapshots")
        print(guid)
        print(image)
        loop t in [0..24): print(cv_type(t))
        print(cv_tpi)
        print(cv_hash)
        print(cv_offs)
    loop text in ["", "A", "AB", "ABC", "ABCD", "abcd", "abcde", "café", "ÄBC"]: print(pdb_hash(text))
    table = pdb_strings()
    saved = table.bytes
    loop text in ["", "first", "first", "É", "second"]: print(pdb_string(table, text))
    assert(saved == [u8(0)], "string-table COW")
    print(pdb_string_table(table))
    print(pdb_gsi([("ABC", 1), ("abc", 8), ("Café", 12), ("café", 32), ("", 64)]))
    loop value in [-9223372036854775807 - 1, -2147483649, -2147483648, -1, 0, 0x7FFF, 0x8000, 2147483647, 2147483648, 9223372036854775807]:
        out: u8[] = [0xAA]
        saved = out
        cv_num(out, value)
        assert(saved == [u8(0xAA)], "numeric-leaf COW")
        print(out)
    out: u8[]
    cv_ranges(out, 3, -1, 0, 0, 200000)
    cv_ranges(out, 0, 6, -40, 13, 90000)
    print(out)
    streams: u8[][] = [[], [u8(42)], fill(u8(3), 4095), fill(u8(4), 4096), fill(u8(5), 4097), [], fill(u8(6), 16385)]
    print(msf(streams))
    loop path in ["", "name.pdb", "/root/name.pdb", "/é/prøgram.pdb"]: print(pdb_name(path))
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_pdb_format_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_state', 'source_types', 'elf_format', 'leb128', 'module_paths', 'json_doc', 'dwarf_format', 'pdb_format')
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
