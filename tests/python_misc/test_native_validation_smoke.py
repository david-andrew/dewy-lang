"""Exercise native language behavior without first building a test compiler."""
import os
import subprocess
from pathlib import Path

import pytest
from test_ambient_effect_boundaries import CASES as ENTRY_CASES
from test_ambient_effect_boundaries import ERRORS as ENTRY_ERRORS
from test_sloppy_bridge import DEWY_CASES
from test_sort_storage_lifetimes import CASES as SORT_CASES
from test_sort_storage_lifetimes import ERRORS as SORT_ERRORS

from udewy.cache import cache_artifact

ROOT = Path(__file__).resolve().parents[2]
CASES = [pytest.param(source, None, id=f'sort-valid-{i}') for i, source in enumerate(SORT_CASES)]
CASES += [pytest.param(source, None, id=f'entry-valid-{i}') for i, source in enumerate(ENTRY_CASES)]
CASES += [pytest.param(source, 'may change its receiver', id=f'sort-invalid-{i}')
          for i, source in enumerate(SORT_ERRORS)]
CASES += [pytest.param(source, 'invalidate a selected dictionary entry', id=f'entry-invalid-{i}')
          for i, source in enumerate(ENTRY_ERRORS)]
CASES += [pytest.param('main=():>int64=>42', None, id='scalar')]
CASES += [pytest.param('''from reporting import Error
import math as numbers
from reporting import Span
main=():>int64=>{let span=Span[0 42] return span.stop as int64}
''', None, id='adjacent-import-forms')]
CASES += [pytest.param(source, None, id=name) for name, source in DEWY_CASES.items()]


@pytest.mark.parametrize(('body', 'diagnostic'), CASES)
def test_native_language_behavior(tmp_path, body, diagnostic):
    compiler = os.environ.get('DEWY_TEST_DRIVER_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_TEST_DRIVER_COMPILER to the current native CLI')
    source = tmp_path / 'main.dewy'
    source.write_text(body)
    env = os.environ | {'DEWY_LIBRARY_ROOT': str(ROOT / 'library'), 'DEWY_FAILURE_LOG': '0'}
    built = subprocess.run([compiler, '-c', source], cwd=tmp_path, env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    binary = tmp_path / cache_artifact(source, cwd=tmp_path)
    if diagnostic is not None:
        assert built.returncode != 0 and diagnostic in built.stderr, built.stdout + built.stderr
        assert not binary.exists()
        return
    assert built.returncode == 0, built.stdout + built.stderr
    result = subprocess.run([binary], capture_output=True, timeout=10, check=False)
    assert result.returncode == 42, (result.returncode, result.stdout, result.stderr)
