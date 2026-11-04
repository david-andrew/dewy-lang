"""Closure layouts and capture cleanup match default/release frozen programs."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


# Both modes exercise distinct generated programs; keep them in the regular tier.
@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize(('case', 'status', 'expected'), [
    ('closure/stack_managed_return', 42, b''),
    ('closure/private_cell_copy', 42, b''),
    ('ownership/spawn_owner_capture', 0, b'in task 3\ndrop\nafter 4\ndrop\n'),
])
def test_lower_closures_twins(compiler, tmp_path, monkeypatch, optimized, case, status, expected):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_closures',),
                         jo_doubles=modules_for(source, output, 'lower_closures',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == status, ran.stderr
    assert ran.stdout == expected
