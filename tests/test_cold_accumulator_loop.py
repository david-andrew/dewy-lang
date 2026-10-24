"""Cold exact-loop allocation preserves live inputs and arbitrary-size results."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_cold_accumulator_loop(compiler, tmp_path, release):
    source = tmp_path / 'accumulate.dewy'
    source.write_text('''sum=(initial:int n:int64 left:string right:string):>int=>{
 let result=initial
 loop i in [0..n) {result+=if left=?right i else -i}
 return result
}
main=()=>{
 printl(sum(0 7 "a" "a"))
 printl(sum(0 7 "a" "b"))
 printl(sum(1267650600228229401496703205376 7 "a" "a"))
 printl(sum(-1267650600228229401496703205376 7 "a" "b"))
 printl(sum(1267650600228229401496703205376 0 "a" "a"))
}
''')
    binary = tmp_path / 'accumulate'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert list(map(int, ran.stdout.split())) == [21, -21, 2**100+21, -2**100-21, 2**100]
