"""A known callback version with one call site moves into its loop on default builds."""
import re
import subprocess

from tests.support import compiler  # noqa: F401
from tools.compiler import bench


def kernel_ir(compiler, tmp_path, name):  # noqa: F811
    source = bench.prepare_source(name, tmp_path)
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', tmp_path / 'program'],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stderr
    return next(b for b in re.split(r'^fn ', built.stdout, flags=re.M) if b.startswith('f_kernel_'))


def test_callback_loop_and_environment_are_in_the_caller(compiler, tmp_path):  # noqa: F811
    for name in ('callbacks', 'callbacks_literal'):
        body = kernel_ir(compiler, tmp_path, name)
        # (only cold failure calls remain, and the environment slots are gone)
        assert not re.search(r' = call .* c=0 ', body), body
        assert ' = slot ' not in body, body
        assert body.count('loop a=') == (2 if name == 'callbacks' else 3), body
