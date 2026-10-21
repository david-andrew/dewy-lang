"""A loop's own element reads are explained without the lowering's names."""
import os
import subprocess

import pytest

from tools.cases import match_patterns
from tests.support import ROOT, compiler  # noqa: F401

CASES = ROOT / 'tests/cases/facts'


@pytest.mark.core_quick
def test_hidden_loop_read_uses_user_terms(compiler):
    result = subprocess.run([compiler, 'check', CASES / 'hidden_loop_read.dewy'],
                            env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'},
                            text=True, capture_output=True, timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert '__' not in output and '$range' not in output, output
    patterns = ["/hidden_loop_read.dewy:3:5: error: cannot prove the loop's element read is in bounds: /",
                'help: establish it with a current guard']
    assert not match_patterns(patterns, output), output
