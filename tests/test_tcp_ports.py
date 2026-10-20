"""TCP listeners keep their ephemeral ports reserved while clients connect."""
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.parametrize('program', ['23_tcp_echo', '24_http_hello'])
@pytest.mark.parametrize('surface', ['core', 'design'])
def test_ladder_tcp_port_isolation(compiler, tmp_path, program, surface):
    binary = tmp_path / 'server'
    built = subprocess.run(
        [compiler, 'build', ROOT / 'tests/ladder' / program / f'{surface}.dewy',
         '-o', binary], capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr

    def run(_):
        result = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    with ThreadPoolExecutor(max_workers=2) as workers:
        outputs = list(workers.map(run, range(8)))
    assert len(set(outputs)) == 1
