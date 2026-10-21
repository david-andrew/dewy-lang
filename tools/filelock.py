"""Exclusive advisory lock on an open file, on POSIX and Windows."""
from __future__ import annotations

import os

if os.name == 'nt':
    import msvcrt

    def lock_exclusive(handle) -> None:
        # Blocks (retrying) until the first byte is ours; released when the file closes.
        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                continue
else:
    import fcntl

    def lock_exclusive(handle) -> None:
        fcntl.flock(handle, fcntl.LOCK_EX)
