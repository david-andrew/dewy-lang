"""The native µDewy compiler, built once per test worker by the Python one."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from udewy.cache import cache_artifact

REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILT: Path | None = None


def native_udewy(directory: Path) -> Path:
    global _BUILT
    if _BUILT is None or not _BUILT.exists():
        main = REPO_ROOT / 'udewy/bootstrap/main.udewy'
        subprocess.run([sys.executable, '-m', 'udewy', '--no-debug-info', '-c', str(main)], cwd=directory, check=True,
                       env={**os.environ, 'PYTHONPATH': str(REPO_ROOT)})
        _BUILT = directory / cache_artifact(main, cwd=directory)
    return _BUILT
