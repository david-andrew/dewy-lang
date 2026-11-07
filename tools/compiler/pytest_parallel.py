"""Keep compact-core compilation batches together without pinning a whole file.

Loaded explicitly by the compact-core gate with pytest-xdist's loadgroup mode.
Other repository tests retain file isolation for their shared build artifacts.
"""
import os
import signal
import time
import zlib

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # Keep expensive files early without passing every file as a separate
    # collection root (which makes pytest repeatedly scan the same directory).
    sizes = {path: path.stat().st_size for path in {item.path for item in items}}
    items.sort(key=lambda item: -sizes[item.path])
    for item in items:
        if item.get_closest_marker('xdist_group') is not None:
            continue
        name = item.path.name
        group = str(item.path)
        if name.startswith('test_core'):
            owner = item.getparent(pytest.Class)
            if owner is not None:
                group = owner.nodeid
            else:
                group += f'::{getattr(item, "originalname", item.name)}'
                callspec = getattr(item, 'callspec', None)
                if callspec is not None:
                    for mode in ('target', 'release'):
                        if mode in callspec.params:
                            group += f'::{mode}={callspec.params[mode]}'
        item.add_marker(pytest.mark.xdist_group(name=group))
    shard(items)


def shard(items: list[pytest.Item]) -> None:
    """DEWY_PYTEST_SHARD=I/N keeps the I-th of N slices (CI runs the slices on separate runners).

    A whole xdist group stays in one slice and every worker computes the same split."""
    spec = os.environ.get('DEWY_PYTEST_SHARD')
    if not spec:
        return
    index, count = (int(part) for part in spec.split('/'))
    assert 0 <= index < count, f'DEWY_PYTEST_SHARD={spec}: expected I/N with 0 <= I < N'

    def owner(item: pytest.Item) -> int:
        group = item.get_closest_marker('xdist_group').kwargs['name']
        return zlib.crc32(group.encode()) % count

    kept = [item for item in items if owner(item) == index]
    dropped = [item for item in items if owner(item) != index]
    if dropped:
        items[0].config.hook.pytest_deselected(items=dropped)
    items[:] = kept


# DEWY_TEST_TRACE=DIR (CI): each process appends the tests it starts to DIR/start-PID.log and,
# when it is sent SIGTERM, records itself, its parent and the test it was running before it
# dies as it would have. An intermittent exit 143 in CI otherwise leaves no trace of who died.
TRACE = os.environ.get('DEWY_TEST_TRACE')
_current = ['']


def _note(name: str, text: str) -> None:
    os.makedirs(TRACE, exist_ok=True)
    with open(os.path.join(TRACE, f'{name}-{os.getpid()}.log'), 'a') as out:
        out.write(f'{time.strftime("%H:%M:%S")} {text}\n')


def pytest_configure(config) -> None:
    if not TRACE:
        return

    def terminated(number, frame):
        _note('sigterm', f'SIGTERM in pid {os.getpid()} (parent {os.getppid()}, group {os.getpgrp()}) '
                         f'running {_current[0]!r}')
        signal.signal(number, signal.SIG_DFL)
        os.kill(os.getpid(), number)

    signal.signal(signal.SIGTERM, terminated)
    _note('start', f'pid {os.getpid()} parent {os.getppid()} group {os.getpgrp()}')


def pytest_runtest_logstart(nodeid: str, location) -> None:
    if TRACE:
        _current[0] = nodeid
        _note('start', nodeid)
