"""A zipped loop's own element reads are proven from its hidden counters."""
import os
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

CASES = ROOT / 'tests/cases/facts'


@pytest.mark.core_quick
def test_hidden_loop_read_is_proven(compiler):
    result = subprocess.run([compiler, '--internal-fact-policy=require-static', 'check', CASES / 'hidden_loop_read.dewy'],
                            text=True, capture_output=True, timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
