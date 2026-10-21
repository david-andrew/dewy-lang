"""`dewy-core test` with no path tests the current directory."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
def test_test_defaults_to_current_directory(compiler, tmp_path):
    (tmp_path / 'adds.dewy').write_text('$test\nadds = () => $expect 1 + 1 =? 2\n')
    result = subprocess.run([compiler, 'test'], cwd=tmp_path, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 passed' in result.stdout, result.stdout + result.stderr
