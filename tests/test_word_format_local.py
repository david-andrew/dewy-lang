"""The checked word writer keeps the exact binding and its formatter semantics."""

import subprocess

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_word_format_local_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = 'tests/cases/word_format_local'
    paths = [f'{cases}/{name}.dewy' for name in ('finite', 'fallback', 'custom')]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_vardecls', 'checks_thin', 'lower_group'),
                             paths, flags=(('--ir',), ('--release',)))
    assert all(result[2] == 0 for result in results), [result[4] for result in results]
    finite, fallback, custom = [result[3] for result in results if result[1] == ('--ir',)]
    assert 'fn f___fmt_word_' in finite
    assert 'fn f___mi_format_' not in finite
    assert 'fn f___mi_format_' in fallback
    assert 'fn f___mi_format_' not in custom


def test_word_format_local_rtos_script_errors(compiler, tmp_path):  # noqa: F811
    source = ROOT / 'tests/ladder/100_rtos_kernel/design.dewy'
    executable = tmp_path / 'rtos'
    built = subprocess.run([compiler, 'build', source, '-o', executable],
                           capture_output=True, text=True, timeout=120, check=False)
    assert built.returncode == 0, built.stderr

    cases = [('yield 1', 'yield', 0), ('work', 'work', 1), ('repeat 1', 'repeat', 2)]
    for operation, name, arity in cases:
        run = subprocess.run([executable], input=f'task t 1\n  {operation}\nrun 1\n',
                             capture_output=True, text=True, timeout=30, check=False)
        assert (run.returncode, run.stdout, run.stderr) == (
            1, f"script line 2: '{name}' takes {arity} operands\n", '')
