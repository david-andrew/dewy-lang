"""Draw context propagation and outside-call witnesses match frozen code."""
import json
import subprocess

import pytest

from tests.selfhost_diagnostic_double import diagnostic_status
from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['direct', 'helpers', 'recursion'])
def test_draw_ops_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/draw_context' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('draw_ops',),
                         jo_doubles=modules_for(source, output, 'draw_ops',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
@pytest.mark.parametrize('case,expected', [('mixed_callers', b'cannot prove drawing'), ('function_value', b'function value'), ('recursion_update', b'outside path')])
def test_draw_ops_diagnostics(compiler, tmp_path, monkeypatch, case, expected):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/draw_context' / (case + '.dewy')).read_text())
    modules = modules_for(source, output, 'draw_ops')
    diagnostic_status(modules, 'fatal')
    driver = "use 'main.jo'\nmain = ():\n    lower_test_cli()\n    print(\"unreachable\")\n"
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('draw_ops',), jo_doubles=modules)
    assert expected in out and b'unreachable' not in out
