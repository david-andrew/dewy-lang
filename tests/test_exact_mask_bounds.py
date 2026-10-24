"""Finite masks prove stores despite a wider mathematical left operand."""
import subprocess

import pytest

from tests.support import compiler
from tests.test_fixed_exact import build


@pytest.mark.parametrize('release', [False, True])
def test_wide_mask_and_floor_power_of_two(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
masked=(a:int64):>int64=>{
    $runtime_checks=false
    return (a*a+12345)&2147483647
}
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    printl(masked(a))
    printl(a%128)
    printl(a//128)
}
''', release)
    for a in [-2**63, -129, -128, -127, -1, 0, 127, 128, 2**63-1]:
        ran = subprocess.run([binary, str(a)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert list(map(int, ran.stdout.split())) == [(a*a+12345)&2147483647, a%128, a//128]
