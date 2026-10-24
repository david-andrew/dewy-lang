"""Positive Dewy remainders supply their existing bounds to exact stores."""
import re
import subprocess

import pytest
from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_positive_modulus_narrows_without_runtime_check(compiler, tmp_path, release):
    source = tmp_path / 'mod.dewy'
    source.write_text(('''digit=(x:int64):>uint8=>uint8(48+x%10)
cycle=(x:int64):>int64=>{
let seed:int64=99
loop i in [0..100) {seed=(seed*1103515245+12345)%2147483648}
return seed+x%97
}
main=(args:array<string>)=>{
let x=int64(to_int(args[1]) ?? 0)
printl(digit(x))
printl(cycle(x))
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'mod'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    bodies = re.split(r'^fn ', built.stdout, flags=re.M)
    for name in ['digit', 'cycle']:
        body = next((b for b in bodies if b.startswith(f'f_{name}_')), None)
        if not release: assert body is not None
        if body: assert 'checked_' not in body and 'overflow_' not in body, body
    seed = 99
    for _ in range(100):
        seed = (seed*1103515245+12345) % 2147483648
    for x in [-2**63, -101, -10, -1, 0, 9, 10, 101, 2**63-1]:
        ran = subprocess.run([binary, str(x)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert list(map(int, ran.stdout.split())) == [48+x%10, seed+x%97]
