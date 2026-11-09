"""Fused workers' driver (forking workers, a worker's lowering and packing, reading the pipes,
replaying journals and placing code here) as a Dewy leaf agrees with frozen Jo: the same bytes and
messages at 1, 2 and 4 workers, which also match one process; failed workers' functions are made here."""
import platform
import sys

import pytest

from tests.selfhost_process_double import compare_workers
from tests.support import compiler  # noqa: F401
from tests.test_core_fused_determinism import CALLBACK_VERSIONS
from tools.compiler.speed import generate_dewy

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'),
    reason='fused workers are x86-64 Linux only')


def test_fused_drive_matches_twin(compiler, tmp_path, monkeypatch):
    (tmp_path / 'synthetic.dewy').write_text(generate_dewy(600))
    (tmp_path / 'versions.dewy').write_text(CALLBACK_VERSIONS + '\n$runtime_checks\n')
    paths = ['synthetic.dewy', 'versions.dewy', 'examples/ring.dewy', 'examples/rollback_model.dewy']
    reports = compare_workers(compiler, tmp_path, monkeypatch, ('fused_drive',), paths)
    assert all('fused: 4 workers' in report for report in reports), reports


@pytest.mark.parametrize('extra', [{'DEWY_FUSED_FAIL_WORKER': '1'}, {'DEWY_FUSED_FAIL': '1'},
                                   {'DEWY_PCHECK_FAIL': 'barrier'}])
def test_fused_drive_failed_workers_match_twin(compiler, tmp_path, monkeypatch, extra):
    (tmp_path / 'synthetic.dewy').write_text(generate_dewy(600))
    compare_workers(compiler, tmp_path, monkeypatch, ('fused_drive',), ['synthetic.dewy'], workers=(2,),
                    extra=extra)
