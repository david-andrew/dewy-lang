"""Allocation failure wrapping preserves rows, results and owner cleanup."""
import json
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['plain', 'owners', 'no_allocates_row'])
def test_oom_ops_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/oom' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('oom_ops',),
                         jo_doubles=modules_for(source, output, 'oom_ops',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == (ROOT / 'tests/cases/oom' / (case + '.out')).read_bytes()
