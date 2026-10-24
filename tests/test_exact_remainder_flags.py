"""Overflow-flag remainder paths preserve the full signed product or sum."""
import random
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_flag_remainder_matches_exact_arithmetic(compiler, tmp_path, release):
    source = tmp_path / 'remainder.dewy'
    source.write_text(('''add=(a:int64 b:int64):>int64=>(a+b)%1000000007
sub=(a:int64 b:int64):>int64=>(a-b)%1000000007
mul=(a:int64 b:int64):>int64=>(a*b)%1000000007
main=(args:array<string>)=>{
let a=int64(to_int(args[1]) ?? 0)
let b=int64(to_int(args[2]) ?? 0)
printl(add(a b))
printl(sub(a b))
printl(mul(a b))
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'remainder'
    built = subprocess.run([compiler, 'build', source, '-o', binary] +
                           (['--release'] if release else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    edge = [-2**63, -2**63+1, -1000000007, -1, 0, 1, 1000000007, 2**63-2, 2**63-1]
    pairs = [(a, b) for a in edge for b in edge]
    rng = random.Random(3961)
    pairs += [(rng.randrange(-2**63, 2**63), rng.randrange(-2**63, 2**63)) for _ in range(40)]
    for a, b in pairs:
        ran = subprocess.run([binary, str(a), str(b)], capture_output=True, text=True)
        assert ran.returncode == 0, (a, b, ran.stderr)
        assert ran.stdout.splitlines() == [str(v % 1000000007) for v in [a+b, a-b, a*b]]


@pytest.mark.parametrize('body', [
    'loop i <? i+2 {i+=1;break}',
    'loop i <? 9223372036854775807 {i+=1;i+=1;break}',
])
def test_induction_does_not_assume_wrapping_guard_or_two_steps(compiler, tmp_path, body):
    source = tmp_path / 'counter.dewy'
    start = 2**63-1 if 'i+2' in body else 2**63-2
    source.write_text((f'''$no_assumed_bounds
main=()=>{{let i:int64={start};{body};printl(i)}}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'counter'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode != 0 and not ran.stdout


def test_remainder_flags_are_not_required_by_wasm(compiler, tmp_path):
    source = tmp_path / 'remainder.dewy'
    source.write_text('''$runtime_checks
$no_assumed_bounds
main=()=>{
let n:int64=4611686018427387904
let total:int64=0
loop i in [int64(-1),1..3) {total+=(i+n)%3}
printl(total)
}
''')
    built = subprocess.run([compiler, 'build', source, '--target', 'wasm32', '-o', tmp_path / 'remainder.html'], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr


def test_doubling_is_not_counter_progress(compiler, tmp_path):
    source = tmp_path / 'doubling.dewy'
    source.write_text('''$runtime_checks
main=()=>{
let n:uint64=9223372036854775808
loop _ in [0..1) {n+=n}
printl(n)
}
''')
    binary = tmp_path / 'doubling'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 101 and not ran.stdout


@pytest.mark.parametrize('release', [False, True])
def test_flag_chain_keeps_cancellation_and_overflow(compiler, tmp_path, release):
    source = tmp_path / 'chain.dewy'
    source.write_text(('''f=(a:int64 b:int64 c:int64):>int64=>a*b+c
main=(args:array<string>)=>{
printl(f(int64(to_int(args[1]) ?? 0) int64(to_int(args[2]) ?? 0) int64(to_int(args[3]) ?? 0)))
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'chain'
    built = subprocess.run([compiler, 'build', source, '-o', binary] + (['--release'] if release else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    lo, hi = -2**63, 2**63-1
    triples = [(lo, -1, -1), (hi, 2, -hi), (2**32, 2**31, lo), (lo, 1, 0), (hi, 1, 1), (lo, -1, 0)]
    rng = random.Random(173)
    triples += [(rng.randint(lo, hi), rng.choice([-3, -1, 0, 1, 2, 3]), rng.randint(lo, hi)) for _ in range(80)]
    for a, b, c in triples:
        expected = a*b+c
        ran = subprocess.run([binary, str(a), str(b), str(c)], capture_output=True, text=True)
        if lo <= expected <= hi:
            assert ran.returncode == 0 and ran.stdout.strip() == str(expected), (a, b, c, ran.stderr, ran.stdout)
        else:
            assert ran.returncode == 101 and not ran.stdout, (a, b, c, ran.stderr, ran.stdout)


@pytest.mark.parametrize('scale,offset', [(2, 1), (3, 1), (3, -1), (7, 2147483647), (7, -2147483647)])
def test_affine_store_checks_exact_preimage(compiler, tmp_path, scale, offset):
    source = tmp_path / 'affine.dewy'
    source.write_text((f'''f=(x:int64):>int64=>{scale}*x+({offset})
main=(args:array<string>)=>printl(f(int64(to_int(args[1]) ?? 0)))
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'affine'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    low = -((-(-2**63-offset)) // scale)
    high = (2**63-1-offset) // scale
    for x in [-2**63, low-1, low, low+1, -1, 0, 1, high-1, high, high+1, 2**63-1]:
        expected = scale*x+offset
        ran = subprocess.run([binary, str(x)], capture_output=True, text=True)
        if -2**63 <= expected < 2**63:
            assert ran.returncode == 0 and ran.stdout.strip() == str(expected), (x, expected, ran.stderr)
        else:
            assert ran.returncode == 101 and not ran.stdout
