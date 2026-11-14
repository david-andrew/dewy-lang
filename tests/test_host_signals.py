"""Signal sources reach a task's listener on the machine running the tests (the CI host-smoke
job's Windows, macOS and arm64 Linux runners, as well as x86-64 Linux): POSIX signals where
there are some, and on Windows Ctrl-Break, a console control event (SetConsoleCtrlHandler).
The listener runs on a task of its own, so this also starts and joins tasks on each host."""
import os
import queue
import signal
import subprocess
import sys
import threading

import pytest

from tests.support import ROOT, compiler  # noqa: F401 (fixture)

WINDOWS = sys.platform == 'win32'
LISTENER = (ROOT / 'tests/cases/signals_delivery/listener.dewy').read_text()


def build(compiler, tmp_path, source, release):
    (tmp_path / 'main.dewy').write_text(source)
    binary = tmp_path / ('listener.exe' if WINDOWS else 'listener')
    built = subprocess.run([compiler, 'build', tmp_path / 'main.dewy', '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=300, cwd=tmp_path)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def deliver(binary, send):
    """Start the listener, wait for its readiness, signal it; its exit status and output."""
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if WINDOWS else 0
    child = subprocess.Popen([binary, 'live'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=flags, env={**os.environ, 'DEWY_NO_AUDIO': '1'})
    lines = queue.Queue()
    reader = threading.Thread(target=lambda: lines.put(child.stdout.readline()), daemon=True)
    reader.start()
    try:
        ready = lines.get(timeout=20)
        assert ready.replace(b'\r\n', b'\n') == b'ready\n', (ready, child.stderr.read())
        send(child)
        out, err = child.communicate(timeout=20)
        return child.returncode, (ready + out).replace(b'\r\n', b'\n').decode(), err.decode(errors='replace')
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)


@pytest.mark.parametrize('release', [False, True])
def test_ctrl_reaches_a_task_listener(compiler, tmp_path, release):
    source = LISTENER.replace('signals.ctrl_c', 'signals.ctrl_break') if WINDOWS else LISTENER
    binary = build(compiler, tmp_path, source, release)
    if WINDOWS:
        status, out, err = deliver(binary, lambda child: os.kill(child.pid, signal.CTRL_BREAK_EVENT))
    else:
        status, out, err = deliver(binary, lambda child: os.kill(child.pid, signal.SIGINT))
    assert (status, out) == (0, 'ready\nctrl-c\nclosed\njoined\n'), err


@pytest.mark.skipif(WINDOWS, reason='POSIX signals')
def test_user_signal_reaches_a_task_listener(compiler, tmp_path):
    source = LISTENER.replace('signals.ctrl_c', 'signals.sigusr2').replace('"ctrl-c"', '"usr2"')
    binary = build(compiler, tmp_path, source, False)
    status, out, err = deliver(binary, lambda child: os.kill(child.pid, signal.SIGUSR2))
    assert (status, out) == (0, 'ready\nusr2\nclosed\njoined\n'), err
