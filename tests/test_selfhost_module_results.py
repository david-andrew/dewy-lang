"""Module-result bookkeeping keeps annotation order and the original first error."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('following, column', [
    ('$runtime_checks', 1),
    ("$build.mode = 'debug'", 1),
    ("if $target.os =? 'none' {let ignored=1}", 1),
    ("if $target.os =? 'linux' {let value=1}", 27),
])
def test_proof_requires_the_next_module_result(compiler, tmp_path, following, column):
    source = tmp_path / 'pending.dewy'
    source.write_text(f'$proof\n{following}\n')
    run = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert run.returncode != 0
    diagnostic = run.stdout + run.stderr
    assert f'{source}:2:{column}: error: $proof requires a function declaration' in diagnostic


@pytest.mark.core_quick
def test_nested_module_groups_keep_declaration_order(compiler, tmp_path):
    source = tmp_path / 'groups.dewy'
    source.write_text('''$runtime_checks
if $target.os =? 'linux' {
    if $build.mode =? 'debug' {const value:int64=41} else {const value:int64=42}
} else {const value:int64=0}
$shadowable const bump:int64=1
printl(value + bump)
''')
    program = tmp_path / 'groups'
    run = subprocess.run([compiler, 'build', source, '-o', program], capture_output=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    run = subprocess.run([program], capture_output=True, timeout=30)
    assert (run.returncode, run.stdout, run.stderr) == (0, b'42\n', b'')
