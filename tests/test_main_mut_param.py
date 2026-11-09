"""A mutable `main` parameter is a clear error, not "could not parse the statement"."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

MESSAGE = ("error: `main`'s parameter cannot be mutable: it receives the command-line arguments "
           "or the program's task group by value, so drop the `@`")


@pytest.mark.parametrize('params', ['@argv', '@args:array<string>', '@app:BackgroundTasks'])
def test_mutable_main_parameter_is_explained(compiler, tmp_path, params):
    (tmp_path / 'main.dewy').write_text(f'main = ({params}) => printl(1)\n')
    result = subprocess.run([compiler, 'run', 'main.dewy'], text=True, capture_output=True, timeout=120, cwd=tmp_path)
    assert result.returncode != 0
    assert MESSAGE in result.stderr, result.stderr
    assert 'could not parse' not in result.stderr, result.stderr
