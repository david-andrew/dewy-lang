"""Hot leaf patterns met moving compiler tables into Dewy: each stays on its fast path."""
import platform
import re
import shutil
import subprocess

import pytest

from tests.support import compiler


def build(compiler, tmp_path, source, flags=(), name='probe'):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source + ('\n$runtime_checks\n' if '$runtime_checks' not in source and '$prototype' not in source else ''))
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
count_newlines=(src:string):>int64=>$unsafe {
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


BESIDE = '''
Table:type=[names:array<string> total:int64]
add=(@t:Table s:string k:int64):>int64=>{
    if k =? 7 {t.names.push(s)}
    t.total+=(s as array<uint8>).length
    t.total
}
table:Table=[names=[] total=0]
wrap=(s:string k:int64):>int64=>add(@table s k)
main=():>void=>{
    let x:int64=0
    loop i in [0..1000) {x+=wrap("hello" i)}
    printl(x)
    printl(table.names.length)
}
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release']])
def test_string_beside_a_place_it_cannot_reach_is_not_retained(compiler, tmp_path, flags):
    binary = build(compiler, tmp_path, BESIDE, flags)
    assert run(binary).split() == ['2502500', '1']
    code = disassembly(binary, 'wrap')
    if code is not None and '<wrap>:' in code:
        assert '__rc_inc' not in code and not re.search(r'\binc\w*\s', code), code


RANGES = '''
same=(a:array<uint8> i:int64 b:string n:int64):>bool=>a[i..i + n) =? (b as array<uint8>)[0..n)
main=():>void=>{
    let a:array<uint8>=[104 101 108 108 111 33]
    printl"{same(a 0 "hello" 5)} {same(a 1 "hello" 5)} {same(a 1 "ello" 4)} {same(a 6 "" 0)}"
}
$runtime_checks
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release']])
def test_byte_ranges_compare_in_place(compiler, tmp_path, flags):
    binary = build(compiler, tmp_path, RANGES, flags)
    assert run(binary).split() == ['true', 'false', 'true', 'true']
    code = disassembly(binary, 'same')
    if code is not None and '<same>:' in code:
        assert '__arr_slice' not in code and '__h_eq' not in code, code


POINTER = '''
total=(p:ptr<uint8> n:int64):>int64=>$unsafe {
    let s:int64=0
    loop i in [0..n) {s+=int64(p[i])}
    s
}
first_words=(a:array<uint8>):>int64=>$unsafe {
    let p=a.ptr
    total(p a.length) + int64((p as ptr<uint16>)[0])
}
main=():>void=>{
    let a:array<uint8>=[1 2 3 4]
    let b=a
    printl"{first_words(a)} {first_words(b)}"
}
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release']])
def test_pointer_only_read_through_copies_nothing(compiler, tmp_path, flags):
    binary = build(compiler, tmp_path, POINTER, flags)
    assert run(binary).split() == ['523', '523']
    code = disassembly(binary, 'first_words')
    if code is not None and '<first_words>:' in code:
        assert 'arruniq' not in code and '__rc_inc' not in code, code


TOKENS = '''
# (a token's loop inside the text's; a bound of a fixed-width parameter)
spaces=(text:array<uint8>):>int64=>{
    let words:int64=0
    let i=0
    loop i <? text.length {
        let start=i
        loop i <? text.length and text[i] not=? 32 {i+=1}
        if i - start >? 0 {words+=1}
        i+=1
    }
    words
}
mix_bytes=(p:ptr<uint8> n:int64):>int64=>$unsafe {
    let h:int64=0
    let i=0
    loop i + 8 <? n {
        h=h xor ((p + i) as ptr<int64>)[0]
        i+=8
    }
    loop i <? n {
        h=h * 31 + int64(p[i])
        i+=1
    }
    h
}
main=():>void=>$unsafe {
    let t:array<uint8>=[97 32 32 98 99 32 100]
    printl"{spaces(t)} {mix_bytes(t.ptr t.length)} {mix_bytes(t.ptr 0)}"
}
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release']])
def test_nested_and_typed_counters_stay_words(compiler, tmp_path, flags):
    binary = build(compiler, tmp_path, TOKENS, flags)
    words, mixed, empty = run(binary).split()
    assert words == '3' and empty == '0'
    for function in ('spaces', 'mix_bytes'):
        code = disassembly(binary, function)
        if code is not None and f'<{function}>:' in code:
            assert '__mi_' not in code, code
