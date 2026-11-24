"""Every process a test starts inherits an empty DISPLAY and WAYLAND_DISPLAY: no window
opens on the desktop. A program that needs pixels renders offscreen (tools/headless.py)."""
import json
import os
from pathlib import Path

import pytest

from tests import leaf_oracle
from tools import headless

ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption('--leaf-oracle', choices=leaf_oracle.MODES, default='expected',
                     help='leaf probe oracle (tests/leaf_oracle.py)')
    parser.addoption('--leaf-capture', default=None, help='directory for --leaf-oracle=capture records')


def pytest_runtest_setup(item):
    leaf_oracle.current = (item.path.stem, item.name)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """After a passing test, the leaf-compiler invocations it made meet their records."""
    try:
        result = yield
    except BaseException:
        leaf_oracle.drop_logs()
        raise
    leaf_oracle.check_logs()
    return result


def pytest_configure(config):
    headless.activate()
    leaf_oracle.configure(config)


def scope_twins(items):
    """`tools.core test --base REV` names the self-hosting test files none of whose inputs changed (see
    tools/twin_scope.py); they join the nightly tier. The counts go back to its summary line."""
    listed, report = os.environ.get('DEWY_TWIN_SCOPED_OUT'), os.environ.get('DEWY_TWIN_SCOPE_REPORT')
    if not report:
        return
    scoped = set(json.loads(Path(listed).read_text())['files']) if listed else set()
    names = {item.path.relative_to(ROOT).as_posix() for item in items if item.path.name.startswith('test_selfhost_')}
    count = 0
    for item in items:
        if item.path.relative_to(ROOT).as_posix() in scoped:
            count += item.get_closest_marker('nightly') is None  # (release runs were nightly already)
            item.add_marker(pytest.mark.nightly)
    Path(report).write_text(json.dumps({'tests': count, 'files': len(scoped & names), 'twin_files': len(names)}))


def pytest_collection_modifyitems(items):
    """A self-hosting test's release-mode run repeats its default-mode run over the same
    leaf; it joins the nightly tier (tools.core test and CI skip it) unless it is core_quick."""
    for item in items:
        params = item.callspec.params if hasattr(item, 'callspec') else {}
        if (item.path.name.startswith('test_selfhost_') and params.get('release') is True
                and item.get_closest_marker('core_quick') is None):
            item.add_marker(pytest.mark.nightly)
    scope_twins(items)
