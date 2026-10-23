"""Hot leaf patterns met moving compiler tables into Dewy: each stays on its fast path."""
import platform
import re
import shutil
import subprocess

import pytest

from tests.support import compiler


def build(compiler, tmp_path, source, flags=(), name='probe'):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    binary = tmp_path / name
    result = subprocess.run([compiler, 'build', path, '-o', binary, *flags],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return binary


def run(binary):
    result = subprocess.run([binary], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def disassembly(binary, function):
    """The function's machine code, or None where it cannot be read."""
    if platform.machine().lower() not in ('x86_64', 'amd64') or not shutil.which('objdump'):
        return None
    return subprocess.check_output(['objdump', '-d', f'--disassemble={function}', binary], text=True)


SCAN = '''
# (unannotated counters: a word-at-a-time scan, then its tail)
count_newlines=(src:string):>int64=>{
    $unsafe
    let c:int64=0
    let n=(src as array<uint8>).length
    let sp=(src as array<uint8>).ptr
    let i=0
    loop i + 8 <=? n {
        let w=((sp + i) as ptr<uint64>)[0] xor 0x0A0A0A0A0A0A0A0A
        if (w - 0x0101010101010101) & (w xor 0xFFFFFFFFFFFFFFFF) & 0x8080808080808080 not=? 0 {
            loop j in [i..i + 8) {
                if sp[j] =? 10 {c+=1}
            }
        }
        i+=8
    }
    loop i <? n and sp[i] not=? 0 {
        if sp[i] =? 10 {c+=1}
        i+=1
    }
    c
}
main=():>void=>{
    loop size in [0 1 7 8 9 15 16 17 100] {
        let bytes:array<uint8>=[]
        loop k in [0..size) {bytes.push(if k % 3 =? 1 10 else 65)}
        printl(count_newlines((bytes as string | none) ?? ""))
    }
}
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release']])
def test_counters_bounded_by_a_length_stay_words(compiler, tmp_path, flags):
    binary = build(compiler, tmp_path, SCAN, flags)
    assert run(binary).split() == [str(len([k for k in range(n) if k % 3 == 1])) for n in [0, 1, 7, 8, 9, 15, 16, 17, 100]]
    code = disassembly(binary, 'count_newlines')
    if code is not None:
        assert '__mi_' not in code, code
