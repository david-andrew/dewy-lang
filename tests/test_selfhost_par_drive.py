"""Parallel emission (forking workers over runs of functions, packing what each made, joining it
here at its new place) as a Dewy leaf agrees with frozen Jo: the same bytes and messages at 1, 2 and
4 workers, which also match one process; a failed worker's run is made here."""
import platform
import sys

import pytest

from tests.selfhost_process_double import compare_workers
from tests.support import compiler  # noqa: F401
from tools.compiler.speed import generate_dewy

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'),
    reason='parallel emission is x86-64 Linux only')

PATHS = ['synthetic.dewy', 'examples/ring.dewy', 'examples/rollback_model.dewy']


def test_par_drive_matches_twin(compiler, tmp_path, monkeypatch):
    (tmp_path / 'synthetic.dewy').write_text(generate_dewy(600))
    reports = compare_workers(compiler, tmp_path, monkeypatch, ('par_drive',), PATHS,
                              extra={'DEWY_FUSED': '0'})
    assert all('emit: 4 workers' in report for report in reports), reports


def test_par_drive_failed_worker_matches_twin(compiler, tmp_path, monkeypatch):
    (tmp_path / 'synthetic.dewy').write_text(generate_dewy(600))
    compare_workers(compiler, tmp_path, monkeypatch, ('par_drive',), PATHS[:1], workers=(2,),
                    extra={'DEWY_FUSED': '0', 'DEWY_EMIT_FAIL_WORKER': '1'})
