"""Opt-in phase observations; never part of cache identity or compiler state."""
from contextlib import contextmanager
from contextvars import ContextVar
import sys
from time import monotonic_ns

_enabled = ContextVar('dewy_phase_timings', default=False)


@contextmanager
def capture(enabled: bool):
    token = _enabled.set(enabled)
    try:
        yield
    finally:
        _enabled.reset(token)


@contextmanager
def phase(name: str):
    started = monotonic_ns() if _enabled.get() else None
    try:
        yield
    finally:
        if started is not None:
            print(f'dewy timing {name} {monotonic_ns() - started} ns', file=sys.stderr)
