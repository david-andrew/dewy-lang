"""`main` takes no parameter, the command-line arguments, or the program's task group: a
second parameter is a clear error naming those, not "could not parse the statement"."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

MESSAGE = ('error: `main` takes at most one parameter: none, the command-line arguments '
           '(`main = (argv) => ...`), or the program\'s task group (`main = (app:BackgroundTasks) => ...`)')


def run(compiler, tmp_path, source):
    (tmp_path / 'main.dewy').write_text(source)
    return subprocess.run([compiler, 'run', 'main.dewy'], text=True, capture_output=True, timeout=120, cwd=tmp_path)


@pytest.mark.parametrize('params', ['a b', 'argv:array<string> n:int64', 'a b c'])
def test_more_than_one_parameter_names_what_main_may_take(compiler, tmp_path, params):
    result = run(compiler, tmp_path, f'main = ({params}) => printl(1)\n')
    assert result.returncode != 0
    assert MESSAGE in result.stderr, result.stderr
    assert 'could not parse' not in result.stderr, result.stderr


@pytest.mark.parametrize('params', ['', 'argv', 'args:array<string>', 'app:BackgroundTasks'])
def test_zero_or_one_parameter_still_works(compiler, tmp_path, params):
    result = run(compiler, tmp_path, f'main = ({params}) => printl(1)\n')
    assert result.returncode == 0 and result.stdout == '1\n', result.stdout + result.stderr
