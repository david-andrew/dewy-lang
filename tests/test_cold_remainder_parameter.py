"""Hot input parameters survive the exact remainder's cold helper call."""
import subprocess

import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_parameter_survives_cold_remainder(compiler, tmp_path, release):
    source = tmp_path / 'remainder.dewy'
    source.write_text(('''digest=(bytes:array<uint8> a:int64 count:int64):>int64=>{
    let total:int64=0
    loop i in [0..count) {
        loop j in [0..3) {
            let value=(a+i)%1000000007
            total+=value+(bytes[j] as int64)
        }
    }
    total
}
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    let count=int64(to_int(args[2]) ?? 0)
    printl(digest([3 as uint8 7 as uint8 11 as uint8] a count))
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'remainder'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    for a in [17, 2**63-1, -(2**63)]:
        for count in [0, 4]:
            ran = subprocess.run([binary, str(a), str(count)], capture_output=True, text=True)
            expected = sum((a+i) % 1000000007 + byte for i in range(count) for byte in [3, 7, 11])
            assert ran.returncode == 0, ran.stdout + ran.stderr
            assert ran.stdout.strip() == str(expected)
