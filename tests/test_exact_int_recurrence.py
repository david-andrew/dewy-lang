"""A rejected recurrence proof must retain the exact fallback."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_fixed_exact import build


@pytest.mark.parametrize('release', [False, True])
def test_variable_range_does_not_assume_positive(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
f=(stop:int64)=>{
 let x=int64(5002)%5003
 loop j in [0..stop) {x=x//3+j}
 return x
}
main=(args:array<string>)=>printl(f(int64(to_int(args[1]) ?? 0)))
''', release)
    for end in [-100, -3, 0, 3, 100]:
        value = 5002
        for j in range(0, end):
            value = value//3+j
        ran = subprocess.run([binary, str(end)], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.strip() == str(value), ran.stdout + ran.stderr
