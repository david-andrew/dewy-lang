"""Storage, COW and temporary cleanup emit identical default/release programs."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


# Both modes exercise distinct generated programs; keep them in the regular tier.
@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize(('case', 'status', 'expected'), [
    ('ownership/fixed_prefix_return', 0, b'ok\n'),
    ('ownership/recursive_owner_copy', 0, b'ok\n'),
    ('closure/copy_cleanup', 42, b''),
])
def test_lower_storage_twins(compiler, tmp_path, monkeypatch, optimized, case, status, expected):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_storage',),
                         jo_doubles=modules_for(source, output, 'lower_storage',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == status, ran.stderr
    assert ran.stdout == expected
