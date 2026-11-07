"""Restarts preserve parsed lazy bodies and still diagnose invalid programs."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.parametrize('eager', [False, True])
@pytest.mark.parametrize('invalid', [False, True])
def test_decimal_restart_lazy_date(compiler, tmp_path, eager, invalid):
    source = (ROOT / 'tests/cases/decimal_restart/lazy_date.dewy').read_text()
    if invalid:
        source = source.replace('printl(total)', 'printl(total.no_such_member)')
    path = tmp_path / 'restart.dewy'
    path.write_text(source)
    result = subprocess.run([compiler, *(['--eager-bodies'] if eager else []),
                             'check', path], capture_output=True, text=True, timeout=30)
    assert result.returncode == (1 if invalid else 0), result.stderr
    assert 'panic:' not in result.stderr
    if invalid:
        assert 'no_such_member' in result.stderr
