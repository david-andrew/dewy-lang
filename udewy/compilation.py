"""Allocation policy for the Python implementations of both compilers.

This does not affect either language's storage semantics. A compilation builds
large, mostly live object graphs; Python's small default allocation threshold
can repeatedly trace the same graph while it is still under construction.
Continue collecting cycles, with more allocations between collections, then
restore the embedding caller's policy when compilation returns or raises.
"""
from contextlib import contextmanager
import gc


@contextmanager
def compiler_allocation_scope():
    previous = gc.get_threshold()
    if not gc.isenabled() or previous[0] == 0 or previous[0] >= 50_000:
        yield
        return
    # A full compiler build holds over a million live syntax/type records.
    # Tracing that graph every 50k allocations repeatedly revisits the same
    # live objects. Keep automatic collection, but amortize it over a larger
    # batch. A caller that already chose a large threshold is left alone.
    gc.set_threshold(500_000, *previous[1:])
    try:
        yield
    finally:
        gc.set_threshold(*previous)
