"""No window and no sound from the test, case, ladder, bench, speed or fuzz harnesses.

`activate()` empties DISPLAY and WAYLAND_DISPLAY (and drops WAYLAND_SOCKET) in this
process's environment, so every child inherits a desktop it cannot reach,
and sets DEWY_NO_AUDIO=1 so games stay silent; `headless(env)`
does the same to an environment built for a child. A program that needs pixels renders
offscreen: DEWY_SOFTWARE=1 with DEWY_SCREENSHOT=FILE.png and DEWY_FRAMES=N.

Only harness entry points call `activate()`: `tools/dewy` and `tools.core run` keep the
caller's display."""
from __future__ import annotations

import os
from typing import MutableMapping

NO_DISPLAY = {'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DEWY_NO_AUDIO': '1'}


def headless(env: MutableMapping[str, str]) -> MutableMapping[str, str]:
    env.update(NO_DISPLAY)
    env.pop('WAYLAND_SOCKET', None)  # an inherited compositor connection
    return env


def activate() -> None:
    headless(os.environ)
