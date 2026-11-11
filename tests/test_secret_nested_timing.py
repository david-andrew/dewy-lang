"""Secret fields and ordering read all bytes; membership does so per element."""
import re
import subprocess

import pytest

from tests.support import compiler
from tests.test_secrets_taken import _counter
from tools.compiler import speed

SOURCE = '''
$runtime_checks

Login:type=[pass:secret<string>]
Pair:type=[first:secret<string> last:secret<string>]
PlainPair:type=[first:string last:string]
ListKey:type=[items:array<secret<string>>]
Nested:type=[left:ListKey right:ListKey]
Key:type=[bytes:secret<array<uint8>>]
BigKey:type=[values:secret<array<int>>]
main=(args:array<string>)=>{
    let chars:array<string>=[]
    loop i in [0..4096) chars.push("a")
    let a=chars.join("")
    if args[2] =? "first" {chars[0]="b"} else {chars[4095]="b"}
    let other=chars.join("")
    let kind=args[1]
    let hits=0
    if kind =? "record" {
        let left=Login[a]
        let right=Login[other]
        loop i in [0..2000) {if left not=? right {hits+=1}}
    } else if kind =? "fields" {
        let left=Pair[a a]
        let same=Pair[a other]
        let different=Pair[other a]
        let right=if args[2] =? "first" different else same
        loop i in [0..2000) {if left not=? right {hits+=1}}
    } else if kind =? "nested" {
        let values:array<secret<string>>=[loop i in [0..64) "a"]
        let changed=values.copy
        if args[2] =? "first" {changed[0]="b"} else {changed[63]="b"}
        let left=Nested[ListKey[values] ListKey[values]]
        let right=if args[2] =? "first" Nested[ListKey[changed] ListKey[values]] else Nested[ListKey[values] ListKey[changed]]
        loop i in [0..2000) {if left not=? right {hits+=1}}
    } else if kind =? "wrapped" {
        let left=secret(PlainPair[a a])
        let right=if args[2] =? "first" secret(PlainPair[other a]) else secret(PlainPair[a other])
        loop i in [0..2000) {if left not=? right {hits+=1}}
    } else if kind =? "bytes" {
        let left=Key[a as array<uint8>]
        let right=Key[other as array<uint8>]
        loop i in [0..2000) {if left not=? right {hits+=1}}
    } else if kind =? "math_array" {
        let raw:array<int>=[loop byte in (a as array<uint8>) int(byte)]
        let changed:array<int>=[loop byte in (other as array<uint8>) int(byte)]
        let left=BigKey[raw]
        let right=BigKey[changed]
        loop i in [0..2000) {if left not=? right {hits+=1}}
    } else if kind =? "contains" {
        let values:array<secret<string>>=[a a]
        loop i in [0..2000) {if not values.contains(secret(other)) {hits+=1}}
    } else if kind =? "order" {
        let left=secret(a)
        loop i in [0..2000) {if (left <? other).reveal {hits+=1}}
    } else {
        loop i in [0..2000) {if a <? other {hits+=1}}
    }
    printl(hits)
}
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_secret_nested_comparison_instructions(compiler, tmp_path, release):
    source, binary = tmp_path / 'compare.dewy', tmp_path / 'compare'
    source.write_text(SOURCE)
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=180)
    assert built.returncode == 0, built.stdout + built.stderr
    counter = _counter()
    counts = {}
    for kind in ('record', 'fields', 'nested', 'wrapped', 'bytes', 'math_array', 'contains', 'order', 'plain'):
        for at in ('first', 'last'):
            instructions, out = counter.run([str(binary), kind, at], speed.clean_env())
            assert out.strip() == '2000', (kind, at, out)
            counts[kind, at] = instructions
    assert counts['plain', 'last'] - counts['plain', 'first'] > 1_000_000, counts
    for kind in ('record', 'fields', 'nested', 'wrapped', 'bytes', 'math_array', 'contains', 'order'):
        assert abs(counts[kind, 'last'] - counts[kind, 'first']) < 1000, (kind, counts)


def test_secret_integer_dictionary_keys_use_full_word_tags(compiler, tmp_path):
    source, binary = tmp_path / 'keys.dewy', tmp_path / 'keys'
    source.write_text('''$runtime_checks

main=()=>{
let keys=dict<secret<int64> int64>()
keys[secret(1)]=42
printl(keys[secret(1)])
}
''')
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    helpers = dict(re.findall(r'fn (f___map_(?:tag|slot_equal)_\d+) ([\s\S]*?)(?=\nfn |\Z)', built.stdout))
    assert len(helpers) == 2, built.stdout
    for name, body in helpers.items():
        assert 'load ' not in body, (name, body)
        if '_tag_' in name:
            assert 'ret a=0 ' in body, body
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert (ran.returncode, ran.stdout, ran.stderr) == (0, '42\n', '')

MATH_SOURCE = '''
$runtime_checks

main=(args:array<string>)=>{
    let a=(to_int(args[3]) ?? 1) << 16384
    let alternatives=[a or 1 a or (1 << 16352)]
    let at=if args[2] =? "first" 0 else 1
    let other=alternatives[at]
    let hits=0
    if args[1] =? "secret" {
        let left=secret(a)
        loop i in [0..2000) {if (left <? other).reveal {hits+=1}}
    } else {
        loop i in [0..2000) {if a <? other {hits+=1}}
    }
    printl(hits)
}
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_secret_integer_ordering_instructions(compiler, tmp_path, release):
    source, binary = tmp_path / 'integer.dewy', tmp_path / 'integer'
    source.write_text(MATH_SOURCE)
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=180)
    assert built.returncode == 0, built.stdout + built.stderr
    counter = _counter()
    counts = {}
    for kind in ('secret', 'plain'):
        for at in ('first', 'last'):
            instructions, out = counter.run([str(binary), kind, at, '1'], speed.clean_env())
            assert out.strip() == '2000', (kind, at, out)
            counts[kind, at] = instructions
    assert abs(counts['plain', 'last'] - counts['plain', 'first']) > 1_000_000, counts
    assert abs(counts['secret', 'last'] - counts['secret', 'first']) < 1000, counts
