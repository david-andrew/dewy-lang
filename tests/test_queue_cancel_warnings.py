"""Cancellation prevents a proof of a permanent no-peer queue wait."""
from pathlib import Path
import subprocess

import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('name', ['channel_cancel_diag_ok', 'mpmc_cancel_diag_ok',
                                  'channel_failure_diag', 'mpmc_failure_diag',
                                  'cancel_helper', 'failure_helper'])
def test_cancelable_no_peer_wait_warns(compiler, tmp_path, name):
    source = Path(__file__).parent / 'cases/queue_cancel_wait' / f'{name}.dewy'
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / name],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    assert 'warning:' in built.stderr, built.stderr
    assert 'group cancellation may end the wait' in built.stderr, built.stderr
