"""Shared debug publication must not depend on x64 allocation being entered."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['aarch64-linux', 'aarch64-mac'])
def test_arm64_debug_lifetime_without_x64_state(compiler, tmp_path, target):  # noqa: F811
    source = tmp_path / 'locals.dewy'
    source.write_text('''$runtime_checks
choose=(value:int64):>int64=>{
    let adjusted=value + 2
    printl(adjusted)
    adjusted
}
printl(choose(40))
''')
    binary = tmp_path / 'locals'
    built = subprocess.run([compiler, 'build', source, '-g', '--target', target,
                            '-o', binary], capture_output=True, timeout=45)
    assert built.returncode == 0, built.stdout + built.stderr
    assert binary.stat().st_size > 0
