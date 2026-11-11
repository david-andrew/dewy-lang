"""A stack overflow on the machine running the tests (the CI host-smoke job's Windows, macOS and
arm64 Linux runners, as well as x86-64 Linux) is reported with the runtime's message and a
nonzero exit, in the main thread, on a `parallel` worker and in a task: never memory
corruption, a hang or a bare signal death."""
import subprocess
import sys

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_cross_target_runs import TASK_OVERFLOW, WORKER_OVERFLOW

EXIT_PANIC = 101

MAIN_OVERFLOW = '''$runtime_checks

depth = (n:int64):>int64 => if n <=? 0 0 else 1 + depth(n - 1)
main = (argv:array<string>):>void => {
    let n = to_int(argv[1]) ?? 0
    if 0 <=? n and n <=? 100000000 {
        printl"{depth(n)} {depth(n + 1)}"
    }
}
'''


def build_native(compiler, tmp_path, source):
    (tmp_path / 'main.dewy').write_text(source)
    binary = tmp_path / ('main.exe' if sys.platform == 'win32' else 'main')
    built = subprocess.run([compiler, 'build', tmp_path / 'main.dewy', '-o', binary], capture_output=True,
                           text=True, timeout=300, cwd=tmp_path)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def run_native(binary, *args):
    ran = subprocess.run([binary, *args], capture_output=True, text=True, errors='replace', timeout=120,
                         cwd=binary.parent)
    return ran.returncode, ran.stdout.replace('\r\n', '\n'), ran.stderr.replace('\r\n', '\n')


def assert_reported(status, err):
    """The runtime said so once and the process exited with the panic status, 101."""
    assert err.count('panic: stack overflow') == 1, err[-2000:]
    assert status == EXIT_PANIC, (status, err[-2000:])


def test_main_thread_stack_overflow_is_reported(compiler, tmp_path):
    binary = build_native(compiler, tmp_path, MAIN_OVERFLOW)
    assert run_native(binary, '1000')[:2] == (0, '1000 1001\n')
    assert_reported(*run_native(binary, '1000000')[::2])


def test_worker_stack_overflow_is_reported(compiler, tmp_path):
    binary = build_native(compiler, tmp_path, WORKER_OVERFLOW)
    assert run_native(binary, '1000')[:2] == (0, '16120\n')
    for _ in range(3):
        assert_reported(*run_native(binary, '1000000')[::2])


@pytest.mark.skipif(sys.platform != 'linux', reason='tasks run on Linux only')
def test_task_stack_overflow_is_reported(compiler, tmp_path):
    binary = build_native(compiler, tmp_path, TASK_OVERFLOW)
    assert run_native(binary, '1000')[:2] == (0, '1000 1001\n')
    assert_reported(*run_native(binary, '1000000')[::2])
