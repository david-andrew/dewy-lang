"""Generated value/ownership helpers agree with the frozen implementation."""
import json
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


@pytest.mark.parametrize(('case', 'status', 'expected'), [
    ('ownership/recursive_owner_copy', 0, b'ok\n'),
    ('sequence/value_protocol_equality_snapshot', 42, b''),
    ('sequence/value_protocol_hash_snapshot', 42, b''),
    ('closure/private_cell_copy', 42, b''),
])
def test_lower_helpers_twins(compiler, tmp_path, monkeypatch, case, status, expected):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_helpers',),
                         jo_doubles=modules_for(source, output, 'lower_helpers'))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == status, ran.stderr
    assert ran.stdout == expected


def test_lower_helpers_invalid_dispatch(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    modules = modules_for(source, output, 'lower_helpers')
    modules['util.jo'], count = re.subn(
        r'(?m)^ice = \(msg: str\):\n(?:[ \t].*\n|\n)*',
        'ice = (msg: str):\n    print(msg)\n    exit(41)\n\n',
        modules['util.jo'], count=1)
    assert count == 1
    driver = ("use 'main.jo'\nuse 'lower.jo'\nuse 'types.jo'\n"
              "use 'lower_primitives.dewy'\n"
              'main = ():\n    lower_test_cli()\n'
              '    lower_helper(lf_helper(HK.parallel_serial, T_INT, 0))\n'
              '    print("unreachable")\n')
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('lower_helpers',), jo_doubles=modules)
    assert out == b'borrowed region helper must lower as an instance\n'
