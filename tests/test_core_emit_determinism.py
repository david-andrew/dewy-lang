"""Emission workers (compiler/par.jo) make the same bytes as one process.

Programs below the fused gate keep 16-byte function alignment, so a worker's run
can land 16 bytes off a 32-byte boundary from where the worker made it, and its
branch pads (cmp_branch_pad) would fall elsewhere. The join moves only functions
whose pads do not depend on that and makes the others again where they land.
"""
import os
import platform
import re
import subprocess
import sys

import pytest

from tests.support import ROOT, compiler

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'),
    reason='emission workers are x86-64 Linux only')

PROGRAMS = [('dunes', []), ('paddle', ['--release']), ('controls', [])]


def build(compiler, name, flags, output, workers):
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(DEWY_EMIT_WORKERS=str(workers), DEWY_PAR_TIME='1', DEWY_CORE_LIB=str(ROOT / 'lib'))
    run = subprocess.run([compiler, 'build', ROOT / 'examples' / f'{name}.dewy', *flags, '-o', output],
                         cwd=output.parent, env=env, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    return output.read_bytes(), run.stderr


def workers_ran(log, workers):
    """How many functions the join made again; fails when the emission workers did not run."""
    found = re.search(rf'emit: {workers} workers, .*, (\d+) functions again here', log)
    assert found, f'the emission workers did not run:\n{log}'
    assert not re.search(r'fused: \d+ workers', log), 'the fused path ran: the program is not below the gate'
    return int(found.group(1))


@pytest.mark.core_quick
def test_ungated_program_one_and_four_workers(compiler, tmp_path):
    one, _ = build(compiler, 'dunes', [], tmp_path / 'one', 1)
    four, log = build(compiler, 'dunes', [], tmp_path / 'four', 4)
    workers_ran(log, 4)
    assert four == one, '4 workers: binary differs from one process'


def test_ungated_programs_any_worker_count(compiler, tmp_path):
    again = 0
    for name, flags in PROGRAMS:
        one, _ = build(compiler, name, flags, tmp_path / f'{name}1', 1)
        for workers in (2, 3, 4):
            got, log = build(compiler, name, flags, tmp_path / f'{name}{workers}', workers)
            again += workers_ran(log, workers)
            assert got == one, f'{name} {flags}, {workers} workers: binary differs from one process'
    # (not vacuous: some run landed off its 32-byte phase and had functions made again)
    assert again > 0
