"""Lifecycle hooks are implicit calls: isolation's own scan must follow them."""
import os
from pathlib import Path
import subprocess

from tests.support import compiler

FIXTURES = Path(__file__).parent / 'fixtures/isolation'


def test_isolation_copy_hook_writing_global(compiler, tmp_path):
    program = tmp_path / 'hooks'
    built = subprocess.run(
        [compiler, 'build', FIXTURES / 'hook_copy.jo', '-o', program],
        capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    library = Path(compiler).parent.parent / 'lib'
    ran = subprocess.run([program, FIXTURES / 'hook_copy.dewy'], capture_output=True, text=True, timeout=60,
                         env=dict(os.environ, DEWY_CORE_LIB=str(library)))
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'hook isolation ok\n'
