"""A failed write to standard output is remembered and reported at the program's end."""
import subprocess
import sys

import pytest

from tests.support import compiler  # noqa: F401

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='/dev/full and SIGPIPE')

MANY = 'main=()=>{\n    loop i in [0..100000) {printl("line {i}")}\n}\n'


def build(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', path, '-o', binary], capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stderr
    return binary


def run_full(binary):
    with open('/dev/full', 'wb') as full:
        return subprocess.run([binary], stdout=full, stderr=subprocess.PIPE, text=True, timeout=60)


@pytest.mark.parametrize('source', [MANY, 'main=()=>printl("x")\n', 'main=()=>{\n    printl("x")\n    exit(3)\n}\n'])
def test_full_device_exits_one_with_report(compiler, tmp_path, source):
    ran = run_full(build(compiler, tmp_path, source))
    assert ran.returncode == 1
    assert ran.stderr == 'error: could not write standard output\n'


def test_good_output_reports_nothing(compiler, tmp_path):
    ran = subprocess.run([build(compiler, tmp_path, 'main=()=>printl("x")\n')], capture_output=True, text=True, timeout=60)
    assert (ran.returncode, ran.stdout, ran.stderr) == (0, 'x\n', '')


def test_closed_pipe_is_quiet(compiler, tmp_path):
    binary = build(compiler, tmp_path, MANY)
    ran = subprocess.run(['bash', '-c', f'set -o pipefail; {binary} | head -1'], capture_output=True, text=True, timeout=60)
    assert ran.stdout == 'line 0\n'
    assert ran.stderr == ''
