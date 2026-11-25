"""Check native image kinds, replacement rules and failures."""
import shutil
import stat

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_dwarf_format import SETUP

pytestmark = pytest.mark.nightly

STEMS = ('checker_types', 'checker_state', 'source_types', 'elf_format', 'pe_format', 'leb128',
         'module_paths', 'json_doc', 'dwarf_format', 'pdb_format', 'native_output')

DRIVER = SETUP + r'''
main = ():
    reset()
    text = fill(u8(0xCC), 64)
    ro = [u8(1), u8(2), u8(3)]
    print(write_elf("program", text, 0, ro, 0x1000))
    print(write_elf("read_only", text, 8, ro, 0x2000))
    print(write_elf("linked", text, 0, [], 0))
    print(write_elf("missing/program", text, 0, ro, 0))
    print(write_elf("directory", text, 0, ro, 0))
    guid = pdb_guid(text)
    print(write_pe("console.exe", text, 0, ro, 0x1000, false, [], [], "", []))
    print(write_pe("window.exe", text, 16, ro, 0x3000, true, [u8(7), u8(8)], [], "window.pdb", guid))
    print(write_pe("read_only.exe", text, 0, [], 0, false, [], [], "", []))
    print(write_pe("missing/window.exe", text, 0, ro, 0, true, [], [], "", []))
    print(write_pdb("window.pdb", guid, 64, fill(u8(0), 200), "src/prøgram.dewy", "test"))
    print(write_pdb("through.pdb", guid, 64, fill(u8(0), 200), "main.dewy", "test"))
    print(write_pdb("missing/window.pdb", guid, 64, [], "main.dewy", "test"))
    print(write_pdb("directory", guid, 64, [], "main.dewy", "test"))
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_native_output_twins(compiler, tmp_path, release):  # noqa: F811
    run = tmp_path / 'run'

    # (a program replaces what stands there; a PDB writes through a link, keeping the target's mode)
    def fresh():
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir()
        (run / 'directory').mkdir()
        for name in ('read_only', 'read_only.exe'):
            (run / name).write_text('stale')
            (run / name).chmod(0o400)
        (run / 'kept').write_text('kept')
        (run / 'linked').symlink_to('kept')
        (run / 'target.pdb').write_text('stale')
        (run / 'target.pdb').chmod(0o640)
        (run / 'through.pdb').symlink_to('target.pdb')
        return run

    output = compare_narrow(compiler, tmp_path, release, STEMS, DRIVER, run_in=fresh)
    assert output.split() == [b'true', b'true', b'true', b'false', b'false',
                              b'true', b'true', b'true', b'false',
                              b'true', b'true', b'false', b'false']
    for names, magic in ((('program', 'read_only', 'linked'), b'\x7fELF'),
                         (('console.exe', 'window.exe', 'read_only.exe'), b'MZ')):
        for name in names:
            path = run / name
            assert not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == 0o755, name
            assert path.read_bytes().startswith(magic), name
    assert (run / 'kept').read_text() == 'kept'
    assert (run / 'through.pdb').readlink().name == 'target.pdb'
    assert stat.S_IMODE((run / 'target.pdb').stat().st_mode) == 0o640
    for name in ('window.pdb', 'target.pdb'):
        assert (run / name).read_bytes().startswith(b'Microsoft C/C++ MSF 7.00')
    assert (run / 'directory').is_dir() and not (run / 'missing').exists()
