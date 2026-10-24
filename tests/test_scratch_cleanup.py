"""Test-run scratch directories go away: on exit, pass or fail, and at the next start for
killed runs; a failed run keeps only its failing cases' outputs, for the newest runs."""
import os
import time

from tools import scratch


def test_runs_are_removed_and_failures_capped(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    monkeypatch.setattr(scratch, '_run', None)
    monkeypatch.setattr(scratch, '_owned', False)
    monkeypatch.delenv('TMPDIR', raising=False)
    root = scratch.tests_root()
    dead = root / 'run-999999999-x'
    live = root / f'run-{os.getppid()}-y'
    dead.mkdir(parents=True)
    live.mkdir()
    for i in range(scratch.KEEP_FAILURES + 2):
        old = root / 'failures' / f'run-1-{i}'
        old.mkdir(parents=True)
        os.utime(old, (time.time() - 100 + i, time.time() - 100 + i))
    run = scratch.activate()
    try:
        assert not dead.exists() and live.exists() and run.is_dir()
        (run / 'build').write_text('big output')
        kept = scratch.record_failure('group/case', 'stdout differs')
    finally:
        scratch.finish(1)
    assert not run.exists()
    assert kept.read_text() == 'stdout differs' and kept.parent.name == run.name
    names = sorted(p.name for p in (root / 'failures').iterdir())
    assert len(names) == scratch.KEEP_FAILURES and run.name in names and 'run-1-0' not in names
