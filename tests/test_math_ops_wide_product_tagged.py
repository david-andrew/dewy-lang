import subprocess

import pytest

from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401


CASE = 'exact_int/wide_product_tagged'


def test_math_ops_twins_wide_product_tagged(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [CASE], leaves=('math_ops',)) == 1


@pytest.mark.parametrize('flags', [('--release',), ('--target', 'web'), ('--target', 'web', '--release')])
def test_wide_product_tagged_across_builds(compiler, tmp_path, flags):
    case = ROOT / 'tests/cases' / CASE
    result = subprocess.run([compiler, 'run', case.with_suffix('.dewy'), *flags],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout == case.with_suffix('.out').read_text()
