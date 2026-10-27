"""Semantic int locals retain exact values across register-width boundaries."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_fixed_exact import build


@pytest.mark.parametrize('release', [False, True])
def test_static_locals_and_reset(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
f=(a:int64 b:int64)=>{
    let x=a+b
    let y=a*b
    printl(x y x+1 x-b y-y)
    if x >? int64.max or x <? int64.min x=a
    printl(int64(x))
    let growing=a+b
    loop _ in [0..3) growing+=growing
    printl(growing)
}
main=(args:array<string>)=>f(int64(to_int(args[1]) ?? 0) int64(to_int(args[2]) ?? 0))
''', release)
    for a, b in [(0, 1), (2**63-1, 1), (-2**63, -1), (-2**63, -2**63), (2**62, 3)]:
        result = subprocess.run([binary, str(a), str(b)], capture_output=True, text=True)
        x = a+b
        expected = [f'{x} {a*b} {x+1} {a} 0', str(a if not -2**63 <= x < 2**63 else x), str(x*8)]
        assert result.returncode == 0 and result.stdout.splitlines() == expected, result.stdout + result.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_unproved_narrowing_still_checks(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
f=(a:int64):>int64=>{
    let x=a+1
    printl(x)
    return x
}
main=(args:array<string>)=>printl(f(int64(to_int(args[1]) ?? 0)))
''', release)
    for a in [2**63-2, 2**63-1]:
        result = subprocess.run([binary, str(a)], capture_output=True, text=True)
        assert (result.returncode == 0) == (a == 2**63-2), result.stdout + result.stderr
        if result.returncode == 0:
            assert result.stdout.splitlines() == [str(a+1)] * 2


@pytest.mark.parametrize('release', [False, True])
def test_broadcast_narrows_at_element_write(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
step=(a:array<int64>):>array<int64>=>a .+ 1
main=(args:array<string>)=>{
    let a:array<int64>=[int64(to_int(args[1]) ?? 0)]
    printl(step(a))
}
''', release)
    for a in [2**63-2, 2**63-1]:
        result = subprocess.run([binary, str(a)], capture_output=True, text=True)
        assert (result.returncode == 0) == (a == 2**63-2), result.stdout + result.stderr
        if result.returncode == 0:
            assert result.stdout.strip() == f'[{a+1}]'
