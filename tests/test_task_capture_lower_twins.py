"""Panic cleanup of task captures survives each lowering leaf's frozen twin."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


@pytest.mark.parametrize('leaf', ['lower_functions', 'lower_helpers', 'lower_group'])
def test_task_capture_cleanup_twins(compiler, tmp_path, monkeypatch, leaf):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    case = ROOT / 'tests/cases/task_capture_panic/order'
    source.write_text(case.with_suffix('.dewy').read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=(leaf,), jo_doubles=modules_for(source, output, leaf))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=10)
    assert ran.returncode == 101, ran.stderr
    assert ran.stdout == case.with_suffix('.out').read_bytes()
