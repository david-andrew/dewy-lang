"""`$program.max_cores` caps the worker pool; no environment variable does."""
import os
import subprocess
import sys

import pytest

from tests.support import compiler  # noqa: F401

THREADS = '''
$runtime_checks

from p"@lib/core/os.jo" import (read_file)
from p"@lib/core/str.jo" import (find)
main=():>void=>{
    let xs=[parallel i in [0..64) i*2]
    let status=read_file("/proc/self/status") ?? "?"
    let at=find(status "Threads:")
    let line=status[at..find(status "\\n" at))
    printl"{xs.length} {line}"
}
'''


def run(compiler, tmp_path, source, command='run', env=None):
    entry = tmp_path / 'app.dewy'
    entry.write_text(source)
    return subprocess.run([compiler, command, entry], capture_output=True, text=True,
                          timeout=90, env=env)


def threads(result):
    assert result.returncode == 0, result.stderr
    count, _, rest = result.stdout.partition(' Threads:')
    assert count == '64'
    return int(rest)


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='counts threads through /proc')
@pytest.mark.parametrize('cores', [1, 2, 3])
def test_header_cap_is_the_threads_including_the_caller(compiler, tmp_path, cores):
    source = f'$program.max_cores = {cores}\n' + THREADS
    assert threads(run(compiler, tmp_path, source)) == cores


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='counts threads through /proc')
def test_no_environment_variable_sets_the_cap(compiler, tmp_path):
    env = dict(os.environ, DEWY_THREADS='1', DEWY_MAX_CORES='1')
    assert threads(run(compiler, tmp_path, '$program.max_cores = 3\n\n' + THREADS, env=env)) == 3


@pytest.mark.parametrize('value', ['0', '-1', '1.5', "'2'", 'two', '007'])
def test_cap_is_a_whole_number_of_at_least_one(compiler, tmp_path, value):
    result = run(compiler, tmp_path, f'$program.max_cores = {value}\n\nmain=()=>printl"x"\n', 'check')
    assert result.returncode != 0
    assert '`$program.max_cores` is a whole number of at least 1' in result.stderr, result.stderr


def test_function_cap_reaches_calls(compiler, tmp_path):
    result = run(compiler, tmp_path, '''report=()=>printl(available_cores)
work=()=>{
 $program.max_cores=1
 report()
}
main=()=>work()
''')
    assert result.returncode == 0, result.stderr
    assert result.stdout == '1\n'


def test_library_cannot_raise_the_callers_cap(compiler, tmp_path):
    (tmp_path / 'lib.dewy').write_text('main=()=>{\n$program.max_cores=4\nprintl(available_cores)\n}\n')
    result = run(compiler, tmp_path,
                 'import p"lib.dewy" as lib\nmain=()=>{\n$program.max_cores=1\nlib.main()\nprintl(available_cores)\n}\n')
    assert result.returncode == 0, result.stderr
    assert result.stdout == '1\n1\n'
