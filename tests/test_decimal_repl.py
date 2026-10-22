"""The prompt's top-level statements: a decimal binding an input declares and writes a float
is a float64; one an earlier input declared ran exact, so a later float write is an error."""
import os
import subprocess

from tests.support import compiler  # noqa: F401


def test_decimal_repl_inputs(compiler, tmp_path):
    text = ('let dt:float64=0.5\nlet acc=0.0; acc+=dt; acc\nacc+=0.25\nacc\n'
            '{\n    let b=0.0\n    b+=dt\n    printl(b)\n}\n'
            'let q=0.1\nq+0.2 =? 0.3\nlet z=1.5\nz+=dt\nz\n:quit\n')
    ran = subprocess.run([compiler, 'repl'], input=text, cwd=tmp_path,
                         env={**os.environ, 'TMPDIR': str(tmp_path)}, capture_output=True,
                         text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['0.5', '0.75', '0.5', 'true', '3/2'], ran.stdout + ran.stderr
    assert ran.stderr.count('error:') == 1 and 'z+=dt' in ran.stderr, ran.stderr
