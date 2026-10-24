"""Scratch space for test runs on the home disk: /tmp is a small memory-backed file system.

One directory per run under the user's cache (`$XDG_CACHE_HOME/dewy/tests`, else
`~/.cache/dewy/tests`; %LOCALAPPDATA% on Windows), named `run-PID-…`. Concurrent runs
keep their own directories. A run removes its directory when it ends, pass or fail; the
next run removes those whose process is gone (killed runs). A failed run's failing cases
keep their outputs in `failures/run-…/`, for the newest KEEP_FAILURES failed runs."""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

KEEP_FAILURES = 5
STALE_HOURS = 48  # a live process this old with a run's PID is a reused PID
_NAMES = ('TMPDIR', 'TMP', 'TEMP')
_run: Path | None = None
_owned = False
_saved = None


def cache_root() -> Path:
    base = os.environ.get('XDG_CACHE_HOME') or (os.environ.get('LOCALAPPDATA') if os.name == 'nt' else '')
    return (Path(base) if base else Path.home() / '.cache') / 'dewy'


def tests_root() -> Path:
    return cache_root() / 'tests'


def remove(path: Path):
    """Remove a tree, read-only files too (Windows); what stays in use is left."""
    def retry(function, name, _):
        try:
            os.chmod(name, 0o700)
            function(name)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if os.name == 'nt':
        # (os.kill would end the process on Windows)
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists
        try:
            code = ctypes.c_ulong()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def sweep(root: Path):
    """Remove run directories whose process is gone (or too old to be its)."""
    cutoff = time.time() - STALE_HOURS * 3600
    for entry in root.glob('run-*'):
        found = re.match(r'run-(\d+)-', entry.name)
        try:
            if found is None or not alive(int(found.group(1))) or entry.stat().st_mtime < cutoff:
                remove(entry)
        except OSError:
            pass


def prune_failures(keep: int = KEEP_FAILURES):
    root = tests_root() / 'failures'
    try:
        runs = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for entry in runs[keep:]:
        remove(entry)


def record_failure(name: str, text: str) -> Path:
    """Keep one failing case's output past the run: failures/<run>/<name>.txt."""
    run = _run.name if _run is not None else f'run-{os.getpid()}-{int(time.time())}'
    directory = tests_root() / 'failures' / run
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (re.sub(r'[^\w.-]', '_', name) + '.txt')
    path.write_text(text, encoding='utf-8', errors='replace')
    return path


def activate() -> Path:
    """This run's scratch directory, made on first use; TMPDIR and tempfile point at it.

    A run inside another run (a gate run by a test) uses its directory."""
    global _run, _owned, _saved
    if _run is not None:
        return _run
    root = tests_root()
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
    """Remove this run's directory, keep the newest failed runs' failure outputs, and put
    the environment back."""
    global _run, _owned, _saved
    if _run is not None and _owned:
        before, tempfile.tempdir = _saved
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        remove(_run)
        prune_failures()
    _run, _owned, _saved = None, False, None


def lock_path(name: str) -> Path:
    """A machine-wide lock file: outside any one run's directory."""
    root = cache_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / name
