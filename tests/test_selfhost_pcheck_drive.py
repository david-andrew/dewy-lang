"""Partitioned root checking (pipes to forked workers, each checking its share of the roots, merged
summaries, failed or rejected workers falling back to one process) as a Dewy leaf agrees with frozen
Jo: the same bytes and messages at 1, 2 and 4 workers, which also match one process."""
import platform
import sys

import pytest

from tests.selfhost_process_double import compare_workers
from tests.support import compiler  # noqa: F401
from tools.compiler.speed import generate_dewy

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'),
    reason='partitioned checking is x86-64 Linux only')


def sources(tmp_path):
    text = generate_dewy(600)
    # (warnings from several partitions, in serial source order)
    for i in (10, 200, 400, 590):
        text = text.replace(f'let s="item {i}"', f'let unused_{i}=1\n    let s="item {i}"')
    (tmp_path / 'roots.dewy').write_text(text)
    (tmp_path / 'late.dewy').write_text(generate_dewy(600).replace('let s="item 590"', 'printl"late {a}"\n    let s="item 590"'))
    (tmp_path / 'errors.dewy').write_text(generate_dewy(600).replace('let s="item 20"', 'let s=not_a_name')
                                          .replace('let s="item 590"', 'let s=another_missing_name'))
    return ['roots.dewy', 'late.dewy', 'errors.dewy']


def test_pcheck_drive_matches_twin(compiler, tmp_path, monkeypatch):
    reports = compare_workers(compiler, tmp_path, monkeypatch, ('pcheck_drive',), sources(tmp_path))
    assert 'pcheck: 4 workers checked 598 roots' in reports[0], reports[0]
    assert 'pcheck: closed-state check rejected' in reports[1], reports[1]


@pytest.mark.parametrize('failure', ['check', 'barrier'])
def test_pcheck_drive_failed_worker_matches_twin(compiler, tmp_path, monkeypatch, failure):
    compare_workers(compiler, tmp_path, monkeypatch, ('pcheck_drive',), sources(tmp_path)[:1], workers=(2,),
                    extra={'DEWY_PCHECK_FAIL': failure})
