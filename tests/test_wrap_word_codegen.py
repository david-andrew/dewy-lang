"""Wrapping literals stay machine words; word boundaries and rotates preserve bits."""
import platform
import re
import subprocess

import pytest
from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_wrap_literals_rotates_and_narrow_operations(compiler, tmp_path, release):
    source = tmp_path / 'words.dewy'
    source.write_text('''W:type=uint32<overflow='wrap'>
Q:type=uint64<overflow='wrap'>
literals=(w:W):>W=>(w+1) xor (w&0xFF) xor (5 xor w)
rotate=(x:W):>W=>(x<<7)|(x>>25)
duplicate=(x:W):>W=>W((Q(x)|(Q(x)<<32))>>9)
product=(x:W y:W):>W=>x*y+x-y
wide_shift=(x:W):>W=>x<<33
main=(args:array<string>)=>{
 let x=W(to_int(args[1]) ?? 0)
 let y=W(to_int(args[2]) ?? 0)
 printl(literals(x))
 printl(rotate(x))
 printl(duplicate(x))
 printl(product(x y))
 printl(wide_shift(x))
}
''')
    binary = tmp_path / 'words'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    bodies = re.split(r'^fn ', built.stdout, flags=re.MULTILINE)
    literal = next((body for body in bodies if body.startswith('f_literals_')), None)
    if not release: assert literal is not None
    if literal is not None: assert ' call ' not in literal, literal
    if platform.machine().lower() in ('x86_64', 'amd64'):
        for name in ['rotate', 'duplicate']:
            body = next((body for body in bodies if body.startswith(f'f_{name}_')), built.stdout)
            assert ' = rot32 ' in body, body
    mask = 2**32-1
    for x in [0, 1, 127, 2**31-1, 2**31, mask]:
        for y in [0, 3, mask]:
            ran = subprocess.run([binary, str(x), str(y)], capture_output=True, text=True)
            assert ran.returncode == 0, ran.stderr
            assert list(map(int, ran.stdout.split())) == [
                ((x+1)&mask) ^ (x&255) ^ (5^x), ((x<<7)|(x>>25))&mask,
                ((x>>9)|(x<<23))&mask, (x*y+x-y)&mask, 0]
