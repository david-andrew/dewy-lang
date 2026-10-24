"""Generated broadcast indexing selects i or zero and needs no assumed bound."""
import subprocess
import pytest
from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_strict_broadcast_indices_without_assumptions(compiler, tmp_path, release):
    source = tmp_path / 'broadcast.dewy'
    source.write_text('''$runtime_checks=false
$no_assumed_bounds
main=()=>{
printl([int(1)] .+ [int(2) int(3)])
printl([int(2) int(3)] .+ [int(1)])
printl([int(2) int(3)] .+ [int(4) int(5)])
let empty:array<int>=[]
printl(empty .+ [int(1)])
}
''')
    result = subprocess.run([compiler, 'run', source, *(['--release'] if release else [])], capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == '[3 4]\n[3 4]\n[6 8]\n[]\n', result.stdout + result.stderr
