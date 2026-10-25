"""Wide and exact integer literals, `concurrent` and `spawn`, comparison chains, `$allocator`,
module-level `$target` chains, `$expect` and `$fail`, stepped and whole slices, generic lambdas and
overload members, and array length conditions, as the direct parser reads them, build as the
reference grammar and projection build them, and report the same mistakes."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROGRAM = '''$runtime_checks
$unsafe
if $target.os =? "windows" {
    width = ():>int64 => 32
} else if $build.mode =? "debug" {
    width = ():>int64 => 64
    tag = ():>string => "debug"
} else {
    width = ():>int64 => 64
    tag = ():>string => "release"
}
zeros = ((n:int64):>array<float64> => [loop i in [0..n) 0.0]) & (<T>(n:int64 fill:T):>array<T> => [loop i in [0..n) fill])
head = <T>(xs:array<T length >? 0>):>T => xs[0]
work = (n:int64):>int64 => n * 2
P:type = [x:int64 y:int64]
$test
expectations = () => {
    let p = P[x=1 y=2]
    let xs = [1 2 3]
    $expect p.x <? p.y, "ordered"
    $expect xs.length =? 3
    $expect not p.x =? 2
    $expect p.x not=? 2
    $expect (p.y) >? 1
}
$test
failing = () => {
    if false { $fail "never" }
    if false { $fail }
}
main = () => {
    let big = 18446744073709551615
    let exact = 340282366920938463463374607431768211456
    let negative = -18446744073709551615
    let based = 0xFF
    let xs = [0 1 2 3 4 5 6 7]
    let lo = 1
    let hi = 6
    let p = P[x=2 y=5]
    printl("{big} {exact} {negative} {based}")
    printl("{0 <? lo <=? hi <? 10} {lo <? work(lo) <? hi =? 6} {p.x <? p.y =? 5}")
    printl("{xs[0,2..]} {xs[end,end-2..0]} {xs[..]} {xs[1,3..6)}")
    let twice = <T>(x:T) => [x x]
    let count = 0
    let bump = <T>(x:T $capture @count) => { count += 1; x }
    printl("{twice(4)} {bump(1)} {bump(2)} {count}")
    printl("{zeros(2)} {zeros(2 7)} {head(xs)} {width()} {tag()}")
    let a = Arena[]
    let n = $allocator(@a) { let ys = [1 2 3]; ys.length }
    let s = $allocator(@a) "a{n}".copy()
    concurrent {
        let t = spawn work(21)
        spawn work(1)
    }
    let total = concurrent g {
        spawn(g) work(4)
    }
    printl("{n} {s} {t} {total is? Canceled}")
}
'''


def test_direct_tasks_identity(compiler, tmp_path):
    source = tmp_path / 'tasks.dewy'
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
    assert outputs[0].startswith(b'18446744073709551615 ')
    tests = []
    for mode in ('old', 'compare'):
        result = subprocess.run([compiler, 'test', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=60)
        tests.append((result.returncode, result.stdout, result.stderr))
    assert tests[0] == tests[1]


@pytest.mark.core_quick
@pytest.mark.parametrize('top,body', [
    ('$expect true', ''), ('f = ():>int64 => {\n$expect true\n1\n}', ''), ('', 'spawn f()'),
    ('', 'let b = 1 <? 2 >? 0'), ('', 'let b = 1 not<? 2 <? 3'), ('', 'let n = $allocator(xs) 1'),
    ('', 'let n = $allocator(@xs) { return }'), ('', 'let ys = xs[0,1,2..]'), ('', 'printl(xs[..)'),
    ('if $target =? "nowhere" { x = 1 }', ''), ('if $target.length >? 2 { x = 1 }', ''),
    ('', 'concurrent 3 { }'), ('', 'let f = <T T>(x:T) => x'), ('', 'let v = 0x"zz"'),
    ('', 'let v = 1_'), ('', '$fail 1 2'), ('h = (<T>(x:T) => x) & (<U>(x:U) => x)', ''),
    ('g = <T>(xs:array<T length in? [1 2]>):>T => xs[0]', '')])
def test_migrated_tasks_diagnostics(compiler, tmp_path, top, body):
    source = tmp_path / 'migrated.dewy'
    source.write_text(f'{top}\nf = ():>void => {{}}\nmain=():>void=>{{\nlet xs = [1]\n{body}\n}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
