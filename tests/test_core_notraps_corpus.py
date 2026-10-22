"""Corpus idioms the no-traps default proves from facts the compiler already sees.

Each PROVED program is checked with `$runtime_checks=false` (the no-traps
policy) and then run, since a proof drops the runtime check. Each REJECTED
program must still report its obligation.
"""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVED = {
    # Masks, shifts and `|`/`xor` of nonnegative values carry ranges into
    # narrowing conversions and table lookups.
    'bit_ranges': ('''$runtime_checks=false
encode=(w:uint32 s:int64 b:uint8 u:uint64):>array<uint8>=>{
    let out:array<uint8>=[]
    out.push((w >> 24) as uint8)
    out.push(((w >> 8) and 255) as uint8)
    if s <? 0 or s >? 0x10ffff return out
    out.push(uint8(0xf0+(s >> 18)))
    out.push(uint8(0x80+((s >> 12) and 0x3f)))
    out.push(((b as int64) xor 64) as uint8)
    out.push((u and 255) as uint8)
    out.push((u >> 56) as uint8)
    out.push(((b as int64) or 1) as uint8)
    out.push(((b >> 4) << 2) as uint8)
    return out
}
lookup=(s:int64 b:uint8):>int64=>{
    let table=[1 2 3 4 5 6 7 8]
    return table[s and 7]+table[int64(b >> 5)]
}
main=():>void=>{
    printl(encode(0x12345678 0x10348 0xc5 0x0102030405060708))
    printl(lookup(-3 0xff))
}
''', '[18 86 240 144 133 8 1 197 48]\n14\n'),
    # A result whose length is an array argument's (plus a small constant) on
    # every return keeps that relation at the call.
    'result_length_follows_argument': ('''$runtime_checks=false
clear_marks=(states:array<bool>):>array<bool>=>{
    let result=states
    loop i in [0..states.length) {result[i]=false}
    return result
}
extended=(xs:array<int64>):>array<int64>=>{
    let out=xs
    out.push(0)
    return out
}
main=():>void=>{
    let states=[loop i in [0..5) true]
    let cleared=clear_marks(states)
    let longer=extended([1 2])
    printl("{cleared[4]} {longer[2]}")
}
''', 'false 0\n'),
    # `fill(x n)` has length n once n is known nonnegative.
    'fill_length': ('''$runtime_checks=false
pick=(n:int64 i:int64):>int64=>{
    if n <? 1 or i <? 0 or i >=? n return 0
    let d=fill(7 n)
    let flags=fill(true n)
    return d[0]+d[i]+(if flags[n-1] 1 else 0)
}
main=():>void=>printl(pick(3 1))
''', '15\n'),
    # A global array only its declaration writes keeps its literal's length.
    'global_table': ('''$runtime_checks=false
let colors=[10 20 30]
let names:array<string>=["a" "bc"]
pick=():>int64=>colors[2]+names[1].length
main=():>void=>printl(pick())
''', '32\n'),
    # A symbolic mask bounds the masked value: a power-of-two ring buffer.
    'ring_mask': ('''$runtime_checks=false
ring=(xs:array<int64> head:int64 i:int64):>int64=>{
    if xs.length =? 0 or head <? 0 or i <? 0 return 0
    let mask=xs.length-1
    return xs[(head+i) and mask]
}
main=():>void=>printl(ring([1 2 3 4] 3 2))
''', '2\n'),
}

REJECTED = {
    'global_resized_at_top_level': ('''$runtime_checks=false
let grown:array<int64>=[1 2]
grow=(@xs:array<int64>):>void=>xs.pop()
grow(@grown)
pick=():>int64=>grown[1]
main=():>void=>exit(pick())
''', 'cannot prove index is in bounds'),
    'global_written_by_a_function': ('''$runtime_checks=false
let values:array<int64>=[1 2]
reset=():>void=>{values=[]}
pick=():>int64=>{reset() return values[1]}
main=():>void=>exit(pick())
''', 'cannot prove index is in bounds'),
    'fill_negative_count': ('''$runtime_checks=false
pick=(n:int64):>int64=>{
    if n >? 5 return 0
    let d=fill(7 n)
    return d[0]
}
main=():>void=>exit(pick(3))
''', 'cannot prove index is in bounds'),
    'result_length_differs_on_one_path': ('''$runtime_checks=false
maybe=(xs:array<int64> k:int64):>array<int64>=>{
    if k >? 0 return []
    return xs
}
main=():>void=>exit(maybe([1 2] 1)[1])
''', 'cannot prove index is in bounds'),
    'mask_too_wide': ('''$runtime_checks=false
lookup=(s:int64):>int64=>{
    let table=[1 2 3 4 5 6 7 8]
    return table[s and 15]
}
main=():>void=>exit(lookup(3))
''', 'cannot prove index is in bounds: missing upper bound'),
    'negative_shift': ('''$runtime_checks=false
lookup=(s:int64):>int64=>{
    let table=[1 2 3 4 5 6 7 8]
    return table[s >> 61]
}
main=():>void=>exit(lookup(3))
''', 'cannot prove index is in bounds'),
    'shift_wraps': ('''$runtime_checks=false
grow=(b:uint8):>uint8=>((b as int64) << 1) as uint8
main=():>void=>exit(int64(grow(3)))
''', 'cannot prove'),
}


def compile_run(compiler, tmp_path, name, source, run=False):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    command = [compiler, 'run', path] if run else [compiler, 'check', path]
    return subprocess.run(command, text=True, capture_output=True, timeout=60)


@pytest.mark.parametrize('name', PROVED)
def test_notraps_corpus_proved(compiler, tmp_path, name):
    source, expected = PROVED[name]
    result = compile_run(compiler, tmp_path, name, source, run=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == expected


@pytest.mark.parametrize('name', REJECTED)
def test_notraps_corpus_rejected(compiler, tmp_path, name):
    source, message = REJECTED[name]
    result = compile_run(compiler, tmp_path, name, source)
    assert result.returncode != 0
    assert message in result.stdout + result.stderr, result.stdout + result.stderr
