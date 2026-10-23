"""`dewy` with no file: the interactive prompt at a terminal, else the program on standard input."""
import os
import subprocess

import pytest

from tests.repl_pty import run_repl
from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source, *flags):
    return subprocess.run([compiler, *flags], input=source, cwd=tmp_path, capture_output=True,
                          text=True, timeout=60, check=False, env={**os.environ, 'TMPDIR': str(tmp_path)})


@pytest.mark.core_quick
def test_piped_stdin_runs_as_a_program(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl"hi"\n')
    assert (ran.returncode, ran.stdout, ran.stderr) == (0, 'hi\n', '')


def test_stdin_redirected_from_a_file(compiler, tmp_path):
    (tmp_path / 'prog.dewy').write_text('printl"from file"\nexit(3)\n')
    with (tmp_path / 'prog.dewy').open() as source:
        ran = subprocess.run([compiler], stdin=source, cwd=tmp_path, capture_output=True,
                             text=True, timeout=60, check=False)
    assert (ran.returncode, ran.stdout) == (3, 'from file\n')


def test_stdin_program_diagnostics_name_stdin(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl(missing_name)\n')
    assert ran.returncode == 1 and ran.stdout == ''
    assert '<stdin>' in ran.stderr and "unknown name 'missing_name'" in ran.stderr


def test_stdin_program_takes_run_flags(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl"fast"\n', '--release')
    assert (ran.returncode, ran.stdout) == (0, 'fast\n')
    ran = run(compiler, tmp_path, 'printl"run"\n', '--release', '--time')
    assert (ran.returncode, ran.stdout) == (0, 'run\n')


def test_stdin_program_uses_files_beside_the_working_directory(compiler, tmp_path):
    (tmp_path / 'helper.dewy').write_text('answer=()=>42\n')
    ran = run(compiler, tmp_path, 'import helper\nprintl(helper.answer())\n')
    assert (ran.returncode, ran.stdout, ran.stderr) == (0, '42\n', '')


def test_empty_stdin_is_an_empty_program(compiler, tmp_path):
    ran = run(compiler, tmp_path, '')
    assert (ran.returncode, ran.stdout, ran.stderr) == (0, '', '')


def test_terminal_stdin_starts_the_prompt(compiler, tmp_path):
    ran = run_repl(compiler, '40+2\n:quit\n', tmp_path)
    assert (ran.returncode, ran.stdout, ran.stderr) == (0, '42\n', '')


def test_repl_is_not_a_command(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl"no"\n', 'repl')
    assert ran.returncode == 1 and ran.stdout == ''
    assert "unknown command 'repl'" in ran.stderr
