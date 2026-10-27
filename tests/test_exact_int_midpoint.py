"""Exact midpoints stay words even when their difference crosses int64."""
import random
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_fixed_exact import build

SOURCE = """mid=(lo:int64 hi:int64)=>lo+(hi-lo)//2
narrow=(lo:int64 hi:int64):>int64=>lo+(hi-lo)//2
change=(@lo:int64):>int64=>{lo=7;return 10}
effect=(lo:int64)=>lo+(change(@lo)-lo)//2
main=(args:array<string>)=>{
 let lo=int64(to_int(args[1]) ?? 0)
 let hi=int64(to_int(args[2]) ?? 0)
 printl(mid(lo hi) narrow(lo hi) effect(lo))
}
"""


@pytest.mark.parametrize('release', [False, True])
def test_exact_midpoint_boundaries_and_effect_order(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, SOURCE, release)
    edge = [-2**63, -2**63+1, -3, -1, 0, 1, 3, 2**63-2, 2**63-1]
    pairs = [(a, b) for a in edge for b in edge]
    rng = random.Random(98)
    pairs += [(rng.randrange(-2**63, 2**63), rng.randrange(-2**63, 2**63)) for _ in range(40)]
    for lo, hi in pairs:
        run = subprocess.run([binary, str(lo), str(hi)], capture_output=True, text=True)
        midpoint = (lo+hi)//2
        assert run.returncode == 0 and run.stdout.strip() == f'{midpoint} {midpoint} {lo+1}', run.stdout + run.stderr
