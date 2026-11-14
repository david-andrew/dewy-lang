"""A CLI's real Ctrl-C handler retains settings and releases its owner normally."""
import os
import signal

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_signals import build, finish, line, start


@pytest.mark.parametrize('release', [False, True])
def test_coverweek_ctrl_c_cleanup_and_policy(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, 'coverweek/signals_helper_policy', release=release)
    child = start(binary, '--wait')
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGINT)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0, err.decode()
        assert out == b'received\nUTC\nreleased\njoined\nUTC\n'
    finally:
        finish(child)
