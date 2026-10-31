"""Every process a test starts inherits an empty DISPLAY and WAYLAND_DISPLAY: no window
opens on the desktop. A program that needs pixels renders offscreen (tools/headless.py)."""
from tools import headless


def pytest_configure(config):
    headless.activate()
