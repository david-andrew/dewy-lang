"""Arm statements, `$extern` bodies, place results, parallel loops, partial operators, pattern
parameters and typed or rest pattern items, membership ranges, call spreads, `$target` chains in
function blocks and live loops, as the direct parser reads them, build as the reference grammar and
projection build them, and report the same mistakes."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROGRAM = '''$runtime_checks
Busy:type = type of error
Account:type = [
    balance:int64
    held:bool
    try_lock = () :> @int64 | Busy => {
        if held return Busy
        return @balance
    }
]
__close_c = (fd:int32):>int32 => $extern(name='close')
apply = (f:<(x:int64):>int64> v:int64):>int64 => f(v)
span = ([first ...middle last]:array<int64 length=4>) => last - first
pair = ([a:int64 b:int64]:array<int64 length=2>) => a * 10 + b
sum3 = (a:int64 b:int64 c:int64):>int64 => a + b + c
bounded = (n:int64):>int64<(in? -100..100)> | none => if n >? 100 none else if n <? -100 none else n
kind = (c:uint8):>string => match c {
    <b'\\{'> => "open"
    _ => "other"
}
first_even = (xs:array<int64>):>int64 => {
    loop x in xs {
        match x % 2 {
            <0> => return x
            _ => continue
        }
    }
    -1
}
platform = ():>string => {
    if $target.os =? "windows" { return "win" } else { let name = "posix" }
    name
}
main = () => {
    let acct = Account[5 false]
    match @(acct.try_lock()) {
        <Busy> => printl("busy")
        b:int64 => printl(b)
    }
    let xs = [1 2 3 4]
    let doubled = [parallel x in xs x * 2]
    parallel @x in xs { x += 1 }
    printl("{doubled} {xs}")
    printl("{apply((*2) 21)} {apply((%10) 42)} {apply((//2) 84)}")
    printl("{span([1 2 3 9])} {pair([4 2])} {sum3([1 2 3]...)}")
    let [p ...rest] = [1 2 3]
    let [[q _] ...] = [[7 8] [9 10]]
    printl("{p} {rest} {q}")
    printl("{3 in? 0..10} {11 not in? 0..10} {4 in? ..} {5 in? ..5} {bounded(7)}")
    printl("{kind(b'\\{')} {first_even([3 5 6 7])} {platform()}")
    let ws = [1 2]
    loop w in @ws {
        if w <? 3 { ws.push(w + 2) }
    }
    printl(ws)
}
'''


def test_direct_statements_identity(compiler, tmp_path):
    source = tmp_path / 'statements.dewy'
    source.write_text(PROGRAM)
    images, outputs = [], []
    for mode in ('old', 'compare'):
        output = tmp_path / mode
        result = subprocess.run([compiler, 'build', source, '-o', output],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        images.append(output.read_bytes())
        ran = subprocess.run([output], capture_output=True, timeout=10)
        assert ran.returncode == 0
        outputs.append(ran.stdout)
    assert images[0] == images[1]
    assert outputs[0] == outputs[1]
    assert b'open 6 posix' in outputs[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('top,body', [
    ('g = (x:int64):>int64 => match x {\n<0> => return\n_ => 1\n}', ''),
    ('c = (fd:int32):>int32 => $extern(name=\'\')', ''), ('c = (fd:int32) => $extern', ''),
    ('c = (@fd:int32):>int32 => $extern', ''), ('c = (fd:int32):>int32 => $extern(nam=\'x\')', ''),
    ('', 'parallel x in xs { return }'), ('', 'let ys = [parallel @x in xs x]'),
    ('', 'parallel x in xs { break }'), ('', 'let f = (*)'), ('', 'let f = ([a a]:array<int64>) => a'),
    ('', 'let [a ...b ...c] = xs'), ('', 'let [...] = xs'), ('', 'let [a... b] = xs'),
    ('', 'printl(1 in? [..0))'), ('h = (x:int64<(in? (0..9])>) => x', ''),
    ('', 'if $target =? "nowhere" { printl(1) }'), ('', 'loop @x in @xs { printl(x) }'),
    ('', 'loop [a] in @xs { printl(a) }'), ('', 'loop x in @xs and y in xs { printl(x) }')])
def test_migrated_statements_diagnostics(compiler, tmp_path, top, body):
    source = tmp_path / 'migrated.dewy'
    source.write_text(f'{top}\nf = ():>void => {{}}\nmain=():>void=>{{\nlet xs = [1]\n{body}\n}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
