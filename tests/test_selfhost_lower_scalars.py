"""Scalar arithmetic, match tables and extreme ranges match the frozen leaf."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


# Both modes exercise distinct generated programs; keep them in the regular tier.
@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize(('case', 'status', 'expected'), [
    ('match/lookup_int_results', 0, b'10\n20\n30\n0\n-7\n100000\n3\n1\n'),
    ('stepped/range_open_extremes', 42, b''),
    ('exact_int/fix_overflow', 0, b'-2 9223372036854775807\n'),
])
def test_lower_scalars_twins(compiler, tmp_path, monkeypatch, optimized, case, status, expected):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_scalars',),
                         jo_doubles=modules_for(source, output, 'lower_scalars',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == status, ran.stderr
    assert ran.stdout == expected
