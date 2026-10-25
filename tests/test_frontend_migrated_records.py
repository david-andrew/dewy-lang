"""Records with methods, imports, `$unsafe`, block settings and labels, loop heads,
comprehensions, dictionaries, ranges, `end`, refinements and the other forms the direct
parser reads build as the reference grammar and projection build them, and report the
same mistakes."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

HELPER = '''$runtime_checks
twice = (x:int64):>int64 => x * 2
'''

PROGRAM = '''$runtime_checks
from p"helper.dewy" import twice
import p"helper.dewy" as h
let drops:int64 = 0
Oops:type = type of error & [message:string]
Leaf = type of [value:int64 label:string = "leaf"]
Sub:type = type of Oops & [code:int64]
Box:type = <T>[value:T]
Mode:type = 'slow' | 'fast'
Positive:type = int64<(>? 0)>
Reading:type = int32<r => -100 <=? r and r <=? 100>
Packet:type = [kind:int64<0 <=? kind and kind <=? 255> seq:int64 = 0]
Account:type = [
    balance:int64 = 0
    deposit = (amount:int64):>void => { balance += amount }
    twice_in = (amount:int64) => { deposit(amount) deposit(amount) }
    sum_to = (n:int64):>int64 => {
        let total = 0
        loop i in [0..n) { total += i + balance }
        let balance = 7
        total + balance
    }
]
Owner = type of [value:int64
    $__drop__
    release = ():>void => { drops += 1 }
]
apply = (f:<(x:int64):>int64> v:int64):>(int64 | Oops) => f(v)
$unsafe
peek = (p:ptr<uint8> i:int64):>uint8 => p[i]
pick = (v:int64|string|bool):>int64 => match v { <bool> => 10 n:int64 => n <string> => 3 }
kind = (b:uint8):>int64 => match b { <b'n'> => 1 _ => 0 }
grid:array<array<int64>> = [[1 2] [3 4]]
printl("top {twice(1)}")
main = () => {
    let a = Account[]
    a.twice_in(2)
    let xs = [10 20 30 40]
    let d = ["a" -> 1 "b" -> 2]
    let s = set[1 2 2]
    let [p q] = [xs[0] xs[end]]
    let evens = [loop i in [0,2..8) if i >? 2 i]
    let pairs = [loop [k v] in [[1 2] [3 4]] k * v]
    let total = 0
    loop i in 0.. and x in xs { total += i * x }
    loop @x in xs { x += 1 }
    $outer loop i in [0..3) {
        loop j in [0..3) { if j =? 2 break $outer; total += 1 }
    }
    { let o = Owner[1] }
    let m:Mode = 'fast'
    let r:Positive = 3
    let bytes:array<uint8> = [1 2 3]
    let first = $unsafe peek(bytes.data() 1)
    printl("{a.sum_to(3)} {d["b"]} {s.length} {p + q} {evens} {pairs} {total} {xs}")
    printl("{drops} {m} {r} {first} {pick(true) + pick(4)} {kind(110)} {h.twice(3)} {[0..3)}")
    printl("{(6 & 3) | 8} {Leaf[1].label} {Box[2].value} {Packet[7].kind} {grid[1][end]}")
    printl(apply((x:int64) => x + 1 41))
}
'''


def test_direct_records_identity(compiler, tmp_path):
    (tmp_path / 'helper.dewy').write_text(HELPER)
    source = tmp_path / 'records.dewy'
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
    assert outputs[0].startswith(b'top 2\n')


@pytest.mark.core_quick
@pytest.mark.parametrize('top,body', [
    ('R:type=[x:int64 x=()=>1]', ''), ('R:type=[main=()=>1]', ''), ('R:type=[$__drop__\nx:int64]', ''),
    ('R:type=[$__drop__\n$__copy__\nf=()=>1]', ''), ('R = type of [x:int64]\nS = type of R & [f=()=>x]', ''),
    ('from p"missing.dewy" import a', ''), ('import a, b', ''), ('from m import a b', ''),
    ('', '$again let x = 1'), ('', '$runtime_checks=1'), ('', 'let n = $unsafe'),
    ('', 'loop @x in @xs {}'), ('', 'loop x in xs as int64 {}'), ('', 'let r = [1..]'),
    ('', 'let f = ((x:int64)=>x) & ((y:string)=>1)'), ('', 'let v = end'),
    ('P:type = int64<(in? 1..5)>', ''), ('Q:type = (x:int64):>int64', ''),
    ('', 'let xs = [1 2] printl(xs[0 [1..]])'), ('', 'let d = ["a" -> 1 2]')])
def test_migrated_records_diagnostics(compiler, tmp_path, top, body):
    source = tmp_path / 'migrated.dewy'
    source.write_text(f'{top}\nmain=():>void=>{{\nlet xs = [1]\n{body}\n}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
