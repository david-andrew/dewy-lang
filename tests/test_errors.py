"""Nominal failures are values; propagation owns and cleans up every exit."""
from pathlib import Path
import subprocess

import pytest

from tests.test_core import compiler, run_value_batch

FIXTURES = Path(__file__).parent / 'fixtures' / 'errors'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_error_values(compiler, tmp_path, release, target):
    cases = {path.stem: path.read_text().replace("__TEST_IO_PATH__", str(tmp_path / "io.txt")) for path in sorted(FIXTURES.glob('*.dewy'))}
    outcomes = run_value_batch(compiler, tmp_path, cases, release, target)
    for name, (code, diagnostic) in outcomes.items():
        assert code == '42', f'{name}: {code}\n{diagnostic}'


@pytest.mark.core_quick
@pytest.mark.parametrize('source,diagnostic', [
    ('E:type=type of error\nfail=():>int64|E=>E\nmain=():>void=>exit(fail() or_throw)',
     'or_throw cannot propagate'),
    ('E:type=type of error\nF:type=type of error\nf=():>int64|E=>F\nmain=():>void=>{f()}',
     'type mismatch'),
    ('E:type=type of error\nf=():>int64|E=>E\nlet x=f() or_throw\nmain=():>void=>{printl(x)}',
     'declared return type'),
    ('E:type=type of error\nmain=():>int64|E=>E', 'main returns void or the errors that reach it'),
    ('A:type=[x:int64]\nB:type=[y:int64]\nf=(b:bool):>A|B=>if b A[1] else B[2]\nmain=():>void=>exit(f(true).x)',
     'has no field'),
    ('A:type=[x:int64]\nE:type=type of error\nf=():>A|E=>A[1]\nmain=():>void=>{let a=f() a.x=2}',
     'union'),
])
def test_error_diagnostics(compiler, tmp_path, source, diagnostic):
    path = tmp_path / 'error.dewy'
    path.write_text(source)
    result = subprocess.run([compiler, 'check', path], capture_output=True, text=True, timeout=30)
    assert result.returncode != 0, result.stdout + result.stderr
    assert diagnostic in result.stdout + result.stderr
