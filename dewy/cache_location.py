"""Where the hosted compiler keeps its transitional pickle caches.

Unpickling executes code, so a cache must come from this user, never from a
project directory that could ship its own `__dewycache__`. Parsed modules and
the checked prelude therefore live in a private per-user directory
(`$XDG_CACHE_HOME/dewy/hosted`, default `~/.cache/dewy/hosted`), keyed by
content digests; a file is loaded only when it and its directory belong to
this user and nobody else can write them. A digest establishes freshness,
not trust. `DEWY_HOSTED_CACHE_DIR` relocates the store (measurement tools use
it to isolate cold runs). These caches are transitional: the final model
builds from source without persistent compiler caches.
"""
from __future__ import annotations

import os
from pathlib import Path


def private_cache_dir(kind: str) -> Path | None:
    """This user's cache directory for `kind`, created private, or None."""
    configured = os.environ.get('DEWY_HOSTED_CACHE_DIR')
    base = Path(configured) if configured else Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'dewy' / 'hosted'
    directory = base / kind
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        return None
    return directory if owned_privately(directory) else None


def owned_privately(path: Path) -> bool:
    """Owned by this user and writable by nobody else."""
    try:
        info = path.stat()
    except OSError:
        return False
    return info.st_uid == os.getuid() and not info.st_mode & 0o022


def trusted_cache_file(path: Path) -> bool:
    return path.is_file() and owned_privately(path) and owned_privately(path.parent)


def staging_path(path: Path) -> Path:
    """A per-process temporary name, so concurrent writers never share one."""
    return path.with_name(f'{path.name}.{os.getpid()}.tmp')
