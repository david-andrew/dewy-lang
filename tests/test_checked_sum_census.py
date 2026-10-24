"""Vector sum guards preserve the scalar prefix-overflow contract."""
import platform
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('kind,values,expected', [
    ('int64', [1, -2, 3, -4] * 16, '-32'),
    ('int64', [-(2**31), 2**31-1] * 16, '-16'),
    ('uint64', [2**32-1] * 32, str((2**32-1)*32)),
    ('int64', [2**63-1, 1, -1], None),
    ('int64', [-2**63, -1, 1], None),
    ('uint64', [2**64-1, 1], None),
    ('int64', [2**63-1, -(2**63-1)], '0'),
    ('int64', [], '0'),
])
def test_checked_sum_census(compiler, tmp_path, release, kind, values, expected):
    path = tmp_path / 'sum.dewy'
    path.write_text(f'main=()=>{{let xs:array<{kind}>=[{" ".join(map(str, values))}]; printl(xs.sum())}}\n')
    binary = tmp_path / 'sum'
    built = subprocess.run([compiler, 'build', path, '--ir', '-o', binary, *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    if len(values) >= 32 and platform.machine().lower() in ('x86_64', 'amd64'):
        assert ' = vld ' in built.stdout, built.stdout
    result = subprocess.run([binary], capture_output=True, text=True)
    if expected is None:
        assert result.returncode != 0 and not result.stdout, result.stdout + result.stderr
    else:
        assert result.returncode == 0 and result.stdout.strip() == expected, result.stdout + result.stderr
