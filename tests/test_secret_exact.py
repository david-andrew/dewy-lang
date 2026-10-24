"""Visibility wrappers do not introduce intermediate integer narrowing."""
import subprocess
import pytest
from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_secret_exact_cancellation(compiler, tmp_path, release):
    source = tmp_path / 'secret_exact.dewy'
    source.write_text('''f=(a:secret<int64> b:int64 c:int64):>secret<int64>=>a*b+c
main=(args:array<string>)=>{
let a=int64(to_int(args[1]) ?? 0)
let b=int64(to_int(args[2]) ?? 0)
let c=int64(to_int(args[3]) ?? 0)
printl(f(a b c).reveal)
}
''')
    binary = tmp_path / 'secret_exact'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    for a, b, c in [(-2**63, -1, -1), (2**63-1, 2, -(2**63-1)), (2**63-1, 1, 1), (-2**63, 2, 2**63-1)]:
        result = a*b+c
        ran = subprocess.run([binary, str(a), str(b), str(c)], capture_output=True, text=True)
        if -2**63 <= result < 2**63:
            assert ran.returncode == 0 and ran.stdout.strip() == str(result), ran.stdout + ran.stderr
        else:
            assert ran.returncode == 101 and not ran.stdout
