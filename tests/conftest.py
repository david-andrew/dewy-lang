"""Scheduling for the parallel gate.

Tests are distributed by file (`--dist loadfile` in pyproject.toml): the tests
that build the same fixture share a worker, so they never race on its
`__dewycache__` artifacts, which are keyed by path alone. With whole files as
the unit, the wall time is set by whichever big file starts last — so the
files marked `slow` (they spawn the CLI, a debugger, an installer) and the
fixture end-to-end file are collected first, and the many small files fill in
behind them.
"""
import pytest

_FRONT = ('test_dewy_test.py', 'test_prototype_mode.py', 'test_cleanparse_udewy_e2e.py', 'test_failure_log.py', 'test_refined_parameters.py', 'test_ide_debugging.py', 'test_assertions.py')


def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    def rank(item: pytest.Item) -> int:
        name = item.path.name
        return _FRONT.index(name) if name in _FRONT else len(_FRONT)
    items.sort(key=rank)   # a stable sort: the order inside each file is kept


# `DEWY_TEST_PROFILE=FILE` appends one line per finished test file: worker,
# file, seconds, and the worker's resident memory before and after it (MB).
# The validation-turnaround measurement (ROADMAP, Phase 1) reads these.
import os
import time

_profile_path = os.environ.get('DEWY_TEST_PROFILE')
_profile_file: list = [None, 0.0, 0]   # current file, its start time, rss at start


def _rss_mb() -> int:
    with open('/proc/self/statm') as statm:
        return int(statm.read().split()[1]) * os.sysconf('SC_PAGE_SIZE') // (1 << 20)


def _profile_flush() -> None:
    name, started, before = _profile_file
    if name is None:
        return
    worker = os.environ.get('PYTEST_XDIST_WORKER', 'main')
    with open(_profile_path, 'a') as out:
        out.write(f'{worker}\t{name}\t{time.monotonic() - started:.1f}\t{before}\t{_rss_mb()}\n')


def pytest_configure(config: pytest.Config) -> None:
    global _profile_path
    # The xdist controller sees every worker's reports; only the process that
    # runs a test records it.
    if _profile_path and not hasattr(config, 'workerinput') and (config.getoption('numprocesses', None) or 0) != 0:
        _profile_path = None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logstart(nodeid: str, location) -> None:
    if not _profile_path:
        return
    name = nodeid.split('::', 1)[0]
    if name != _profile_file[0]:
        _profile_flush()
        _profile_file[:] = [name, time.monotonic(), _rss_mb()]


def pytest_sessionfinish(session: pytest.Session) -> None:
    if _profile_path:
        _profile_flush()
