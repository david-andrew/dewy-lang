"""Regression tests for nightly fuzz findings (2026-11-27):
- x64 baseline match lookup table signed subtraction overflow on wide int64 literals
- x64 baseline per-arm scoping for match/if value arms with managed bindings
- facts inventory misclassifying dense integer-keyed dict literals as arrays
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
