"""Joining a parallel worker's run (its code, fixups, symbols, line rows, unwind and debugger tables
moved to where the run lands) as a Dewy leaf agrees with frozen Jo: the same bytes with debug
information and in release builds, at 2 and 4 workers, which also match one process."""
import platform
import sys

import pytest

from tests.selfhost_process_double import compare_workers
from tests.support import compiler  # noqa: F401
from tools.compiler.speed import generate_dewy

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'),
    reason='parallel emission is x86-64 Linux only')


def test_par_join_debug_and_release_match_twin(compiler, tmp_path, monkeypatch):
    (tmp_path / 'synthetic.dewy').write_text(generate_dewy(600))
    reports = compare_workers(compiler, tmp_path, monkeypatch, ('par_drive',),
                              ['synthetic.dewy', 'examples/rollback_model.dewy'],
                              extra={'DEWY_FUSED': '0'}, flags=(('-g',), ('--release',)))
    assert all('emit: 4 workers' in report for report in reports), reports
