"""Frozen line-section bytes with sparse file IDs and retained source snapshots."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_dwarf_format import SETUP

DRIVER = SETUP + r'''
main = ():
    reset()
    dbg_raw = []; dbg_cfi = []; global_ids = []
    files = []
    loop i in [0..130): files.push(SrcFile(path="source/é-{i}.dewy"))
    ir_positions = [0]
    line_rows = []
    # First-use order differs from file order; invalid files and synthetic
    # positions exercise skipped rows and line-zero transitions.
    loop i in [0..400):
        file = if i % 7 == 0: 150 else: (129 - i % 130)
        ir_positions.push((file << 40) | i)
        line_rows.push(i * 8); line_rows.push(i + 1)
        line_rows.push(i * 8 + 2); line_rows.push(i + 1)
        if i % 13 == 0: line_rows.push(i * 8 + 4); line_rows.push(0)
    saved_files = files; saved_rows = line_rows; saved_positions = ir_positions
    loop arm0 in [false, true]:
        arm = arm0
        print(dwarf_image(0x400000, 3200, "main.dewy", "test", "/build"))
        assert(files == saved_files and line_rows == saved_rows and ir_positions == saved_positions)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_dwarf_borrowed_file_index(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_state', 'source_types', 'elf_format',
             'leb128', 'module_paths', 'json_doc', 'dwarf_format')
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
