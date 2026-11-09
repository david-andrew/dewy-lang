"""`int?` and `ptr<T>?` are one word (zero: none), and the debug info says so: a debugger sees a type
over that word, not a value beside a `has` flag (lib/debug's printers read zero as none)."""
import platform
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

SOURCE = '''Holder:type = [id:int64 slot:int? at:ptr<uint8>?]
probe = ():>void => $unsafe {
    let buf:array<uint8> = [7 8 9]
    let none_int:int? = none
    let small:int? = 5
    let zero:int? = 0
    let big:int? = -123456789012345678901234567890
    let none_ptr:ptr<uint8>? = none
    let some_ptr:ptr<uint8>? = buf.ptr
    let held = Holder[1 none buf.ptr]
    printl(held.id)
    printl(none_int small zero big none_ptr isnt? none some_ptr isnt? none)
}
main = ():>void => probe()
'''
LINE = 12


def build(compiler, tmp_path):  # noqa: F811
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        pytest.skip('native Linux x86-64 required')
    source = tmp_path / 'probe.dewy'
    source.write_text(SOURCE)
    binary = tmp_path / 'probe'
    built = subprocess.run([compiler, 'build', source, '-g', '-o', binary], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    return source, binary


def test_gdb_shows_one_word_optionals(compiler, tmp_path):  # noqa: F811
    if not shutil.which('gdb'):
        pytest.skip('gdb required')
    source, binary = build(compiler, tmp_path)
    printer = compiler.parent.parent / 'lib/debug/dewy_gdb.py'
    commands = ['whatis small', 'print/r none_int', 'print/r small', 'print/r zero', 'whatis none_ptr', 'print/r none_ptr',
                'print/r held.slot']
    args = ['-ex', 'info locals']
    for command in commands:
        args += ['-ex', f'echo @{command}\\n', '-ex', command]
    ran = subprocess.run(['gdb', '--batch', '-nx', '-ex', f'source {printer}', '-ex', f'break {source}:{LINE}', '-ex', 'run',
                          *args, str(binary)], capture_output=True, text=True, timeout=60)
    out = ran.stdout + ran.stderr
    for line in ['none_int = none', 'small = 5', 'zero = 0', 'big = -123456789012345678901234567890',
                 'none_ptr = none', 'some_ptr = 0x', 'held = [id=1 slot=none at=0x']:
        assert line in out, out
    # (what gdb sees: one word each, so no `value` and `has`; 5 is 10 with its low bit flipped, none is 0)
    shown = dict(zip(commands, (part.split('\n')[1] for part in out.split('@')[1:])))
    assert shown['whatis small'] == 'type = int?', out
    assert [shown[f'print/r {name}'] for name in ('none_int', 'small', 'zero')] == ['$1 = 0', '$2 = 11', '$3 = 1'], out
    assert shown['print/r held.slot'] == '$5 = 0', out
    if not shown['whatis none_ptr'].startswith('type = struct'):
        assert shown['whatis none_ptr'] == 'type = ptr<uint8>?', out
        assert shown['print/r none_ptr'] == '$4 = (ptr<uint8>?) 0x0', out


def test_pdb_describes_one_word_optionals_as_their_word(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'word.dewy'
    source.write_text('Holder:type = [id:int64 slot:int?]\nmain = ():>void => {\n    let a:int? = 5\n    printl(Holder[1 a].slot)\n}\n')
    two_words = tmp_path / 'two.dewy'
    two_words.write_text('main = ():>void => {\n    let b:int64? = 7\n    printl(b)\n}\n')
    for path in (source, two_words):
        built = subprocess.run([compiler, 'build', path, '--target', 'x86_64-windows', '-g', '-o', tmp_path / f'{path.stem}.exe'],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        pdb = (tmp_path / f'{path.stem}.pdb').read_bytes()
        # (an `int64?` is a struct, a value beside a `has` flag, named `optional<int>`; an `int?` is the word)
        assert (b'optional<int>@' in pdb) == (path is two_words), path
