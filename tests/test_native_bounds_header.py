"""Native bounds checks select a valid zero-length header for nil arrays."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('values', ['', '7 9'])
@pytest.mark.parametrize('index', [-1, 0, 1, 2])
def test_native_bounds_header(compiler, tmp_path, values, index):
    source = tmp_path / 'bounds.dewy'
    source.write_text((f'''$no_assumed_bounds
read=(xs:array<int64> at:int64):>int64=>{{return xs[at]}}
main=()=>{{let xs:array<int64>=[{values}]; printl(read(xs {index}))}}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'bounds'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    if values and index in (0, 1):
        assert ran.returncode == 0 and ran.stdout.strip() == values.split()[index]
    else:
        assert ran.returncode == 101 and 'out of bounds' in ran.stderr, ran.stdout + ran.stderr
