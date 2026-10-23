"""Scratch space for test runs on the home disk: /tmp is a small memory-backed file system.

One directory per run under the user's cache (`$XDG_CACHE_HOME/dewy/tests`, else
`~/.cache/dewy/tests`; %LOCALAPPDATA% on Windows). Concurrent runs keep their own
directories; one is removed when its run succeeds, and any older than STALE_HOURS
are removed by the next run."""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

STALE_HOURS = 6
_NAMES = ('TMPDIR', 'TMP', 'TEMP')
_run: Path | None = None
_owned = False
_saved = None


def cache_root() -> Path:
    base = os.environ.get('XDG_CACHE_HOME') or (os.environ.get('LOCALAPPDATA') if os.name == 'nt' else '')
    return (Path(base) if base else Path.home() / '.cache') / 'dewy'


def sweep(root: Path, hours: float = STALE_HOURS):
    cutoff = time.time() - hours * 3600
    for entry in root.glob('run-*'):
        try:
            if entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            pass


def activate() -> Path:
    """This run's scratch directory, made on first use; TMPDIR and tempfile point at it.

    A run inside another run (a gate run by a test) uses its directory."""
    global _run, _owned, _saved
    if _run is not None:
        return _run
    root = cache_root() / 'tests'
    root.mkdir(parents=True, exist_ok=True)
    inherited = Path(os.environ.get('TMPDIR', ''))
    if inherited != Path() and inherited.parent == root and inherited.is_dir():
        _run, _owned = inherited, False
        return _run
    sweep(root)
    _run, _owned = Path(tempfile.mkdtemp(prefix=f'run-{os.getpid()}-', dir=root)), True
    _saved = ({name: os.environ.get(name) for name in _NAMES}, tempfile.tempdir)
    for name in _NAMES:
        os.environ[name] = str(_run)
    tempfile.tempdir = str(_run)
    return _run


def finish(status: int):
    """Remove this run's directory after a success (a failed run's stays for inspection)
    and put the environment back."""
    global _run, _owned, _saved
    if _run is not None and _owned:
        if status == 0:
            shutil.rmtree(_run, ignore_errors=True)
        before, tempfile.tempdir = _saved
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    _run, _owned, _saved = None, False, None


def lock_path(name: str) -> Path:
    """A machine-wide lock file: outside any one run's directory."""
    root = cache_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / name
