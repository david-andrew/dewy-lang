"""The sensor formatter handles the entire declared signed input domain."""
from pathlib import Path
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_sensor_signed_magnitude(compiler, tmp_path, release):
    program = (Path(__file__).parent/'ladder/112_bulletproof_sensor/design.dewy').read_text()
    degrees = 'degrees = ' + program.split('degrees = ', 1)[1].split('\nmain = ', 1)[0]
    values = [-2**63, -11, -1, 0, 1, 11, 2**63-1]
    source = tmp_path/'magnitude.dewy'
    source.write_text('$bulletproof\n' + degrees + '\n' +
                      '\n'.join(f'printl(degrees({v}))' for v in values))
    result = subprocess.run([compiler, *(['--release'] if release else []), source],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f'{"-" if v < 0 else ""}{abs(v)//10}.{abs(v)%10}' for v in values
    ]
