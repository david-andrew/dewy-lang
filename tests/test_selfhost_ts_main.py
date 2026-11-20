"""The main thread's allocator state word (__ts_main): each leaf that names it builds the same program as its twin."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('leaf', ['lower_functions', 'lower_group', 'checker_program'])
def test_ts_main_twins(compiler, tmp_path, monkeypatch, optimized, leaf):  # noqa: F811
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    case = ROOT / 'tests/cases/ownership/main_thread_state'
    source.write_text(case.with_suffix('.dewy').read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver, extra_stems=(leaf,),
                         jo_doubles=modules_for(source, output, leaf,
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=60)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == case.with_suffix('.out').read_bytes()
