"""Every process a test starts inherits an empty DISPLAY and WAYLAND_DISPLAY: no window
opens on the desktop. A program that needs pixels renders offscreen (tools/headless.py)."""
import pytest

from tools import headless


def pytest_configure(config):
    headless.activate()


def pytest_collection_modifyitems(items):
    """A twin differential test's release-mode run repeats its default-mode run over the same
    leaf; it joins the nightly tier (tools.core test and CI skip it) unless it is core_quick."""
    for item in items:
        params = item.callspec.params if hasattr(item, 'callspec') else {}
        if (item.path.name.startswith('test_selfhost_') and params.get('release') is True
                and item.get_closest_marker('core_quick') is None):
            item.add_marker(pytest.mark.nightly)
