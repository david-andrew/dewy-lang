"""Literal parallel-region endpoints are real proofs, even without axioms."""
import subprocess
import pytest
from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_parallel_literal_parameter_bounds(compiler, tmp_path, release):
    source = tmp_path / 'bounds.dewy'
    source.write_text('''$runtime_checks=false
$no_assumed_bounds
main=()=>{
printl([parallel i in [0..5) i*i])
printl([parallel i in [-3..3] i*i])
}
''')
    binary = tmp_path / 'bounds'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout.splitlines() == ['[0 1 4 9 16]', '[9 4 1 0 1 4 9]'], ran.stdout + ran.stderr
