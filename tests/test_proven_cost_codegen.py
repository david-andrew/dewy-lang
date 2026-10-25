"""Boolean complements use one comparison without changing operand evaluation."""
import re
import subprocess

import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_integer_complement_and_float_comparisons(compiler, tmp_path, release):
    source = tmp_path / 'complements.dewy'
    source.write_text('''$runtime_checks
predicate=(x:int64 f:int64):>bool=>(x and f) not=? 0
less=(x:int64 y:int64):>bool=>not (x <? y)
ule=(x:uint64 y:uint64):>bool=>not (x <=? y)
float_less=(x:float64 y:float64):>bool=>not (x <? y)
main=(args:array<string>)=>{
 let x=int64(to_int(args[1]) ?? 0)
 let y=int64(to_int(args[2]) ?? 0)
 printl(predicate(x y))
 printl(less(x y))
 printl(ule(x transmute uint64 y transmute uint64))
 printl(float_less(float64(x) float64(y)))
 printl(float_less(uint64(9221120237041090560) transmute float64 0.0))
}
''')
    binary = tmp_path / 'complements'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    if not release:
        bodies = re.split(r'^fn ', built.stdout, flags=re.M)
        for name in ('predicate', 'less', 'ule'):
            body = next(b for b in bodies if b.startswith(f'f_{name}_'))
            assert ' = xor ' not in body, body
        assert ' = ne ' in next(b for b in bodies if b.startswith('f_predicate_'))
    for x, y in [(0, 0), (1, 0), (0, 1), (-1, 1), (1, -1),
                 (-(2**63), 2**63-1), (2**63-1, -(2**63))]:
        ran = subprocess.run([binary, str(x), str(y)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        expected = [bool(x & y), x >= y, x % 2**64 > y % 2**64, float(x) >= float(y), True]
        assert ran.stdout.split() == [str(b).lower() for b in expected]
