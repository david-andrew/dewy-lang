"""`dewy build --exit-codes` prints main's exit-code table and builds nothing."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''Late:type=type of error
Early:type=type of error & [why:string]
Offline:type=type of error & [exit_code:int64=1]
step=(n:int64)=>{
    if n =? 1 return Late
    if n =? 2 return Early["two"]
    if n =? 3 return Offline[]
    return n
}
main=()=>{
    printl(step(args().length) or_throw)
}
'''


def test_exit_code_table(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    built = subprocess.run([compiler, 'build', '--exit-codes', source], capture_output=True,
                           text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    # (declaration order; Offline pins 1, so the others take the next free codes)
    assert built.stdout.splitlines() == ['0 success', '2 Late', '3 Early', '1 Offline (its exit_code)',
                                         '101 a panic']
    assert not (tmp_path / 'main').exists()
