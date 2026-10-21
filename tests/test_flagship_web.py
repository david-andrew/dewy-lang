"""Tier-4 flagships on the wasm target: the ladder runs them natively; here the same
program is built for the web and run under Node, and must print the same expected.out.
The notes UI page shell is built for the web too (it needs a browser to run)."""
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import Scripts, compiler  # noqa: F401 (fixture)

LADDER = Path(__file__).resolve().parent / 'ladder'


def build_web(compiler, source, output, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', output, '--target', 'wasm', *flags],
                           capture_output=True, text=True, timeout=120, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    return output.with_suffix('.html')


@pytest.mark.parametrize('program', ['97_notes_service'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_flagship_runs_on_wasm(compiler, tmp_path, program, release):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is needed to execute the generated web runner')
    page = build_web(compiler, LADDER / program / 'design.dewy', tmp_path / 'program', release)
    scripts = Scripts()
    scripts.feed(page.read_text())
    runner = tmp_path / 'program.cjs'
    runner.write_text('\n'.join(scripts.parts))
    ran = subprocess.run([node, runner], capture_output=True, timeout=60, check=False)
    assert ran.returncode == 0, ran.stderr.decode(errors='replace')
    assert ran.stdout.decode() == (LADDER / program / 'expected.out').read_text()
