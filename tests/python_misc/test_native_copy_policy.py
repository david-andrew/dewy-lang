"""Rejected copy policies do not run the native backend."""
import os
import subprocess
from pathlib import Path

import pytest
from test_strict_copy_policy import SOURCE

from udewy.cache import cache_artifact

ROOT = Path(__file__).resolve().parents[2]


def test_native_copy_policy_rejects_before_emission(tmp_path):
    compiler = os.environ.get('DEWY_TEST_DRIVER_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_TEST_DRIVER_COMPILER to the current native CLI')
    source = tmp_path / 'main.dewy'
    source.write_text('$explicit_copies\n' + SOURCE)
    native_map = tmp_path / 'native.map'
    env = os.environ | {'DEWY_LIBRARY_ROOT': str(ROOT / 'library'),
                        'DEWY_NATIVE_MAP': str(native_map), 'DEWY_FAILURE_LOG': '0'}
    result = subprocess.run([compiler, '--timings', '-c', source], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode != 0 and 'unproven copy' in result.stderr, result.stdout + result.stderr
    assert 'dewy timing lowering.native ' not in result.stderr
    assert not native_map.exists()
    assert not (tmp_path / cache_artifact(source, cwd=tmp_path)).exists()
