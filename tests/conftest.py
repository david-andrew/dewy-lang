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
