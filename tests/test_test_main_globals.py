"""`dewy test` does not run main: a test that reads a global only main gives a value
is a compile error (it would read no value), not a silent zero."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

MESSAGE = "`dewy test` does not run main, so tests see only what the top level gives it"

FAILING = {
    'reads_main_global': 'let y:int64\nmain = () => {\n    y = 3\n    printl(y)\n}\n$test\nreads = () => $expect y =? 3\n',
    'helper_reads_main_global': 'let y:int64\nmain = () => { y = 3 }\nhelper = ():>int64 => y + 1\n'
                                '$test\nreads = () => $expect helper() =? 4\n',
    # (each test starts from the top level's state: one test's assignment is not another's)
    'other_test_assigns': 'let y:int64\n$test\nsets = () => {\n    y = 4\n    $expect y =? 4\n}\n'
                          '$test\nreads = () => $expect y =? 4\n',
}

PASSING = {
    'top_level_gives_value': 'let y:int64\ny = 2\nmain = () => { y = 3 }\n$test\nreads = () => $expect y =? 2\n',
    'test_assigns_first': 'let y:int64\nmain = () => { y = 3 }\n$test\nown = () => {\n    y = 5\n    $expect y =? 5\n}\n',
    'test_skips_global': 'let y:int64\nmain = () => { y = 3 }\n$test\nplain = () => $expect 1 + 1 =? 2\n',
}


def run_test(compiler, tmp_path, name, source):  # noqa: F811
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'test', str(path)], capture_output=True, text=True, timeout=60, check=False)


@pytest.mark.parametrize('name', sorted(FAILING))
def test_main_only_global_is_an_error(compiler, tmp_path, name):  # noqa: F811
    result = run_test(compiler, tmp_path, name, FAILING[name])
    assert result.returncode == 102, result.stdout + result.stderr
    assert "reads 'y' before it is given a value" in result.stderr and MESSAGE in result.stderr, result.stderr


@pytest.mark.parametrize('name', sorted(PASSING))
def test_given_global_passes(compiler, tmp_path, name):  # noqa: F811
    result = run_test(compiler, tmp_path, name, PASSING[name])
    assert result.returncode == 0, result.stdout + result.stderr
