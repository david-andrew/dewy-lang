"""The net module compiles for every native target: Windows (Winsock), macOS
(libSystem) and Linux on both processors. The golden cases in tests/cases/net run
the loopback programs on this machine; here the same programs (those without
tasks, which are Linux's for now) must build for the others."""
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

CASES = Path(__file__).resolve().parent / 'cases' / 'net'


@pytest.mark.parametrize('program', ['echo', 'errors'])
@pytest.mark.parametrize('target', ['x86_64-windows', 'aarch64-mac', 'aarch64-linux'])
def test_net_builds_for_target(compiler, tmp_path, program, target):
    built = subprocess.run([compiler, 'build', CASES / f'{program}.dewy', '--target', target,
                            '-o', tmp_path / program], capture_output=True, text=True, timeout=120, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
