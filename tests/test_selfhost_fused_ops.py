"""Fused partition workers' records, validation, replay maps and emission, and the parallel
workers' word encoding, agree with frozen Jo: the same bytes and messages at 1, 2 and 4 workers,
which also match one process."""
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


def test_fused_matches_twin(compiler, tmp_path, monkeypatch):
    (tmp_path / 'synthetic.dewy').write_text(generate_dewy(600))
    (tmp_path / 'versions.dewy').write_text(CALLBACK_VERSIONS + '\n$runtime_checks\n')
    paths = ['synthetic.dewy', 'versions.dewy', 'examples/ring.dewy', 'examples/rollback_model.dewy']
    reports = compare_workers(compiler, tmp_path, monkeypatch, ('fused_ops', 'par_ops'), paths)
    # (not vacuous: the fused workers ran)
    assert all('fused: 4 workers' in report for report in reports), reports
