"""Sparse exact preparation covers conversions and falls back for storage/control."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_fixed_exact import build


@pytest.mark.parametrize('release', [False, True])
def test_conversion_roots_and_control(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
pure=(a:int64 b:int64):>float64=>float64((a*b)-a)
controlled=(a:int64 b:int64):>float64=>float64(if a >? 0 {a*b} else {-a*b})
local=(a:int64 b:int64):>float64=>{
    let ignored:float64=0.0
    loop i in [0..3) ignored+=float64(i)
    return float64(a*b)+ignored
}
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    let b=int64(to_int(args[2]) ?? 0)
    printl(pure(a b) =? float64(int(a)*int(b)-int(a)))
    printl(controlled(a b) =? float64(abs(int(a))*int(b)))
    printl(local(a b) =? float64(int(a)*int(b))+3.0)
}
''', release)
    for a, b in [(2**63-1, 513), (-2**63, -1), (2**62+127, 1025)]:
        ran = subprocess.run([binary, str(a), str(b)], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.splitlines() == ['true'] * 3, ran.stdout + ran.stderr


@pytest.mark.parametrize('release', [False, True])
def test_conversion_does_not_hide_store(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
mixed=(a:int64 b:int64):>float64=>{
    let rounded=float64(a*b)
    let stored:int64=a*b
    return rounded+float64(stored)
}
main=(args:array<string>)=>printl(mixed(int64(to_int(args[1]) ?? 0) 3))
''', release)
    ran = subprocess.run([binary, str(2**62)], capture_output=True, text=True)
    assert ran.returncode != 0 and not ran.stdout, ran.stdout + ran.stderr


@pytest.mark.parametrize('release', [False, True])
def test_power_of_two_conversion_rounds_once(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
f=(a:int64):>float64=>float64(a*8)
g=(a:int64):>float32=>float32(a*4611686018427387904)
wide=(a:int64):>float64=>float64((a*a)*8)
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    printl(f64_bits(f(a)) =? f64_bits(float64(int(a)*8)))
    printl(f32_bits(g(a)) =? f32_bits(float32(int(a)*4611686018427387904)))
    printl(wide(a) =? float64(int(a)*int(a)*8))
}
''', release)
    for a in [0, 1, -1, 2**63-1, -2**63, 2**62+127, 2**53+1, -(2**53+1)]:
        ran = subprocess.run([binary, str(a)], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.splitlines() == ['true'] * 3, ran.stdout + ran.stderr
