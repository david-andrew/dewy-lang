"""Regression tests for nightly fuzz findings (2026-11-27):
- x64 baseline match lookup table signed subtraction overflow on wide int64 literals
- x64 baseline per-arm scoping for match/if value arms with managed bindings
- facts inventory misclassifying dense integer-keyed dict literals as arrays
- bitwise facts reading an open `int` end of an exact product as int64.max (2026-11-28)
"""
import subprocess

import pytest

from tests.support import compiler


def _build_and_run(compiler, tmp_path, name, source, *, release=False):
    src = tmp_path / f'{name}_{"rel" if release else "dbg"}.dewy'
    exe = tmp_path / f'{name}_{"rel" if release else "dbg"}'
    src.write_text(source)
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', src, '-o', exe, *flags],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    return subprocess.run([exe], capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize('release', [False, True])
def test_match_wide_int64_literals_no_table_overflow(compiler, tmp_path, release):
    source = r'''
$runtime_checks

Color:type = 'red' | 'green' | 'blue' | 'cyan'

pick = (x:int64):>Color => {
    let n:Color = match x {
        <0> => 'green'
        <100> => 'blue'
        <7677809479657208295> => 'cyan'
        <-9223372036854775807> => 'red'
        <5281328281532756924> => 'blue'
        _ => 'red'
    }
    n
}

main = ():>void => {
    let xs:array<int64> = [-9223372036854775808 -9223372036854775807 0 100 5281328281532756924 7677809479657208295 9223372036854775807]
    loop v in xs { printl(pick(v)) }
}
'''
    ran = _build_and_run(compiler, tmp_path, 'wide_match', source, release=release)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['red', 'red', 'green', 'blue', 'blue', 'cyan', 'red']


@pytest.mark.parametrize('release', [False, True])
def test_union_match_arm_managed_binding_scoped(compiler, tmp_path, release):
    source = r'''
$runtime_checks

choose = (u:int64|string):>string => {
    let res:string = (match u {
        m7:string => (if (int64(-10) =? int64(-4)) "{"line"}{""}" else m7)
        m8:int64 => "x=1"
    })
    return res
}

main = ():>void => {
    let n:int64 = -13
    let r:[value:int64 xs:array<int64>] = [xs=[15 n n] value=n]
    let u1:int64|string = n
    let u2:int64|string = "hello"
    printl(choose(u1))
    printl(choose(u2))
    printl((match u1 { m1:int64 => "ok" m2:string => (match n { <0> => m2 _ => u1 }) }))
    printl(r)
}
'''
    ran = _build_and_run(compiler, tmp_path, 'union_match_scope', source, release=release)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['x=1', 'hello', 'ok', '[value=-13 xs=[15 -13 -13]]']


@pytest.mark.parametrize('release', [False, True])
def test_dense_int_dict_membership_not_refuted(compiler, tmp_path, release):
    source = r'''
$runtime_checks
$no_assumed_bounds

main = ():>void => {
    let d:dict<int64 int64> = [1->(-8) 2->14 0->4611686018427387904]
    $runtime_assert ((-11) in? d) =? false
    $runtime_assert (1 in? d) =? true
    let (a b c d2) = ["one" "two" "three" "four"]
    printl("{a} {b} {c} {d2}")
}
'''
    ran = _build_and_run(compiler, tmp_path, 'dense_dict_in', source, release=release)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == 'one two three four'


@pytest.mark.parametrize('release', [False, True])
def test_match_uint64_crossing_and_short_circuit_unscoped(compiler, tmp_path, release):
    source = r'''
$runtime_checks

classify_u64 = (x:uint64):>int64 => match x {
    <9223372036854775807> => 10
    <9223372036854775808> => 20
    <9223372036854775809> => 30
    <9223372036854775810> => 40
    _ => 50
}

classify_u64_wide = (x:uint64):>int64 => match x {
    <0> => 1
    <1> => 2
    <9223372036854775808> => 3
    <18446744073709551615> => 4
    _ => 5
}

pick = (flag:bool seed:string):>string => {
    let b:string? = if flag none else "kept"
    let c = b ?? (let tmp = "fallback-{seed}"; tmp)
    let ok = flag and (let tag = "tag-{c}"; tag.length >? 0)
    if ok "{c}:1" else "{c}:0"
}

main = ():>void => {
    printl(classify_u64(uint64(9223372036854775807)))
    printl(classify_u64(uint64(9223372036854775808)))
    printl(classify_u64(uint64(0)))
    printl(classify_u64_wide(uint64(0)))
    printl(classify_u64_wide(uint64(18446744073709551615)))
    printl(classify_u64_wide(uint64(7)))
    loop i in [0..4) { printl(pick(i % 2 =? 0 "v{i}")) }
}
'''
    ran = _build_and_run(compiler, tmp_path, 'u64_short_circuit', source, release=release)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['10', '20', '50', '1', '4', '5',
                                       'fallback-v0:1', 'kept:0', 'fallback-v2:1', 'kept:0']


@pytest.mark.parametrize('release', [False, True])
def test_captured_int64_square_bitwise_stays_exact(compiler, tmp_path, release):
    # seed 4610887 (2026-11-28): `n*n` of an int64 is an `int` in [0, open);
    # `and` with a negative mask read the open end as int64.max and lowered
    # the product as one wrapped word.
    source = r'''
$runtime_checks
$no_assumed_bounds

main = ():>void => {
    let n2:int64 = (int64(-8) - int64(4611686018427387904))
    let fn7 = (s9:int64 $capture @n2):>int64 => { n2 }
    printl(n2)
    printl"= {((n2 * n2) and n2)}"
    let (v17 v18 v19 ...rest20) = [int64(n2) int64(0) int64(n2)]
    printl(rest20)
}
'''
    ran = _build_and_run(compiler, tmp_path, 'open_square_and', source, release=release)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['-4611686018427387912', '= 21267647932558654040247889259323719744', '[]']
