"""An explicitly unsafe extraction must still explain a lost parameter write."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('flags', [[], ['--release']])
def test_data_write_unsafe_warning(compiler, tmp_path, flags):
    source = tmp_path / 'unsafe.dewy'
    source.write_text('''
write=(xs:array<int64>):>void=>$unsafe {
    let p=xs.data()
    p[0]=42
}
main=()=>{let xs:array<int64>=[10] write(xs) printl(xs)}
''')
    binary = tmp_path / 'unsafe'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    assert "warning: data() of plain parameter 'xs'" in built.stderr
    assert 'take `@xs`' in built.stderr and 'copy into a local first' in built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=20)
    assert ran.returncode == 0 and ran.stdout == '[10]\n', ran.stdout + ran.stderr
