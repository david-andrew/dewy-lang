"""Successful index checks refine their values without discharging themselves."""
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('policy', ['$runtime_checks', '$prototype'])
def test_checked_index_retains_first_obligation(compiler, tmp_path, policy):
    source = tmp_path / 'checked.dewy'
    source.write_text(policy + '\n'
                      'work=(xs:array<int64> i:int64)=>{printl(xs[i]) printl(xs[i])}\n'
                      'main=()=>work([7] 0)\n')
    result = subprocess.run([compiler, 'check', '--obligations', source],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    sites = [line for line in result.stdout.splitlines() if 'runtime check: index' in line]
    assert len(sites) == 1, result.stdout + result.stderr


def test_checked_index_no_circular_loop_proof(compiler):
    source = Path(__file__).parent / 'cases/checked_index/loop_recheck.dewy'
    result = subprocess.run([compiler, 'check', '--obligations', source],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'runtime check: index' in result.stdout, result.stdout + result.stderr
