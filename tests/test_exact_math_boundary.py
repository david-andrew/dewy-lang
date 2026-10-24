"""Fixed-width operands retain their exact high words at mathematical-int boundaries."""
import subprocess

import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_exact_math_boundary(compiler, tmp_path, release):
    source = tmp_path / 'boundary.dewy'
    source.write_text('''add=(a:int64 b:int64):>int=>a+b
sub=(a:int64 b:int64):>int=>a-b
mul=(a:int64 b:int64):>int=>a*b
neg=(a:int64):>int=>-a
power=(a:int64):>int=>a^3
shift=(a:int64):>int=>a<<63
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    let b=int64(to_int(args[2]) ?? 0)
    printl(add(a b)); printl(sub(a b)); printl(mul(a b))
    printl(neg(a)); printl(power(a)); printl(shift(a))
    let value:int=a+b
    printl(value)
}
''')
    binary = tmp_path / 'boundary'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    for a, b in [(2**63-1, 1), (-(2**63), -1), (3037000500, 3037000500), (7, -3)]:
        ran = subprocess.run([binary, str(a), str(b)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert list(map(int, ran.stdout.split())) == [a+b, a-b, a*b, -a, a**3, a<<63, a+b]
