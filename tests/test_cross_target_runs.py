"""Programs whose behavior once differed by target, run on each: x86-64 Linux natively,
aarch64 Linux under qemu-aarch64, x86-64 Windows under Wine in the sloppy-wine container."""
import platform
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

WINE_IMAGE = 'localhost/sloppy-wine:latest'
TARGETS = ['x86_64-linux', 'aarch64-linux', 'x86_64-windows']


def wine_ready():
    podman = shutil.which('podman')
    return podman is not None and subprocess.run([podman, 'image', 'exists', WINE_IMAGE], capture_output=True,
                                                 timeout=30).returncode == 0


def build(compiler, tmp_path, source, target, *flags):
    (tmp_path / 'main.dewy').write_text(source)
    binary = tmp_path / ('main.exe' if 'windows' in target else 'main')
    built = subprocess.run([compiler, 'build', tmp_path / 'main.dewy', '--target', target, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=300, cwd=tmp_path)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def run(target, binary, *args, setup=''):
    """Run a built program on its target: (exit status, stdout, stderr)."""
    if target == 'x86_64-linux':
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            pytest.skip('needs an x86-64 Linux host')
        command = [binary, *args]
    elif target == 'aarch64-linux':
        if (runner := shutil.which('qemu-aarch64')) is None:
            pytest.skip('no qemu-aarch64')
        command = [runner, binary, *args]
    else:
        if not wine_ready():
            pytest.skip(f'the Windows run needs podman and {WINE_IMAGE}')
        script = f'{setup} wine /w/{binary.name} "$@"'
        command = ['podman', 'run', '--rm', '-e', 'LANG=C.UTF-8', '-v', f'{binary.parent}:/w:z', WINE_IMAGE,
                   'sh', '-c', script, 'sh', *args]
    ran = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=300, cwd=binary.parent)
    return ran.returncode, ran.stdout.replace('\r\n', '\n'), ran.stderr.replace('\r\n', '\n')


# Every iteration overflows its stack, on the main thread and on the pool's workers at once:
# each worker's stack ends in a guard and has its own signal stack, so the first overflow is
# reported (once) and nothing runs into a neighbouring worker's stack.
WORKER_OVERFLOW = """$program.max_cores = 4
$runtime_checks
depth = (n:int64):>int64 => if n <=? 0 0 else 1 + depth(n - 1)
main = (argv:array<string>):>void => {
    let n = to_int(argv[1]) ?? 0
    if 0 <=? n and n <=? 100000000 {
        printl([parallel s in [0..16) depth(n + s)].sum)
    }
}
"""


@pytest.mark.parametrize('target', TARGETS)
def test_worker_stack_overflow_is_reported(compiler, tmp_path, target):
    binary = build(compiler, tmp_path, WORKER_OVERFLOW, target)
    assert run(target, binary, '1000')[:2] == (0, '16120\n')
    for _ in range(3):
        status, out, err = run(target, binary, '1000000')
        assert status == 101, (status, err[-2000:])
        assert err.count('panic: stack overflow') == 1, err[-2000:]
