"""Native signal delivery is confined to the subprocess owned by each test."""
import os
from pathlib import Path
import selectors
import signal
import sys
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

if sys.platform != 'linux':
    pytest.skip('Linux task backend', allow_module_level=True)


def build(compiler, tmp_path, case=None, source=None, release=False):
    path = ROOT / 'tests/cases' / f'{case}.dewy' if case else tmp_path / 'main.dewy'
    if source is not None:
        path.write_text(source)
    target = tmp_path / 'listener'
    result = subprocess.run([compiler, 'build', path, '-o', target, *(['--release'] if release else [])],
                            capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return target


def line(child):
    # Raw, unbuffered pipes avoid hiding already-read lines from select().
    with selectors.DefaultSelector() as waiting:
        waiting.register(child.stdout, selectors.EVENT_READ)
        output = bytearray()
        while not output.endswith(b'\n'):
            assert waiting.select(timeout=10), f'child {child.pid} did not publish readiness'
            byte = os.read(child.stdout.fileno(), 1)
            assert byte, child.stderr.read().decode()
            output += byte
        return output.decode()


def start(binary, *arguments):
    return subprocess.Popen([binary, *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                            env={**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DEWY_NO_AUDIO': '1'})


def finish(child):
    if child.poll() is None:
        child.kill()
    child.communicate(timeout=10)


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('case,sig,label', [
    ('signals_delivery/listener', signal.SIGINT, 'ctrl-c'),
    ('signals_observe/listener', signal.SIGWINCH, 'resize'),
    ('signals_multiple/listener', signal.SIGUSR2, 'usr2'),
])
def test_delivery(compiler, tmp_path, release, case, sig, label):
    binary = build(compiler, tmp_path, case, release=release)
    child = start(binary, 'live')
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, sig)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0, err.decode()
        assert out.decode() == f'{label}\nclosed\njoined\n'
    finally:
        finish(child)


def test_observer_preserves_ctrl_c_default(compiler, tmp_path):
    binary = build(compiler, tmp_path, source='''import p"@lib/std/signals.dewy" as signals
Cleanup:type = [word:int64 $__drop__=():>void=>printl"cleaned"]
main = () => {
    let cleanup = Cleanup[0]
    _ = signals.ctrl_c.observe.next(timeout=0s)
    printl"ready"
    sleep(30s) or_throw
}
''')
    child = start(binary)
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGINT)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 130, (out, err, child.returncode)
        assert b'cleaned\n' in out  # first press requests normal cleanup
    finally:
        finish(child)


@pytest.mark.parametrize('import_signals', [False, True])
def test_unused_sources_install_nothing(compiler, tmp_path, import_signals):
    prefix = 'import p"@lib/std/signals.dewy" as signals\n' if import_signals else ''
    if import_signals:
        prefix += 'let saved = signals.ctrl_c.observe\n'
    binary = build(compiler, tmp_path, source=prefix + '''main = () => {
    printl"ready"
    sleep(30s) or_throw
}
''')
    child = start(binary)
    try:
        assert line(child) == 'ready\n'
        status = Path(f'/proc/{child.pid}/status').read_text()
        caught = int(next(row.split()[1] for row in status.splitlines() if row.startswith('SigCgt:')), 16)
        public = [signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGWINCH, signal.SIGUSR1, signal.SIGUSR2]
        assert all(not caught & (1 << (sig - 1)) for sig in public)
        os.kill(child.pid, signal.SIGINT)
        child.communicate(timeout=10)
        assert child.returncode == -signal.SIGINT
    finally:
        finish(child)


@pytest.mark.parametrize('release', [False, True])
def test_busy_handler_coalesces_and_drains_before_close(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, release=release, source='''import p"@lib/std/signals.dewy" as signals
main = () => {
    let started = channel<bool>(2)
    let busy = channel<bool>(1)
    let release = channel<bool>(1)
    concurrent {
        spawn {
            _ = signals.sigusr1.next(timeout=0s)
            started.send(true) or_throw
            let first = true
            loop event in signals.sigusr1 {
                if first {
                    first = false
                    busy.send(true) or_throw
                    printl"busy"
                    release.receive or_throw;
                } else { printl"coalesced" }
            }
            printl"drained"
            printl"{signals.sigusr1.observe.next(timeout=0s) is? Closed}"
        }
        spawn {
            _ = signals.sigusr2.next(timeout=0s)
            started.send(true) or_throw
            loop _ in signals.sigusr2 { release.send(true) or_throw }
        }
        started.receive or_throw;
        started.receive or_throw;
        printl"ready"
        busy.receive or_throw;
    }
    printl"joined"
}
''')
    child = start(binary)
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGUSR1)
        assert line(child) == 'busy\n'
        for _ in range(12):
            os.kill(child.pid, signal.SIGUSR1)
        # The first handler remains ordinary activity until this independent
        # signal releases it. Its coalesced pending notification must drain.
        os.kill(child.pid, signal.SIGUSR2)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0, err.decode()
        assert out == b'coalesced\ndrained\ntrue\njoined\n'
    finally:
        finish(child)


def test_independent_owners_broadcast_and_restore(compiler, tmp_path):
    binary = build(compiler, tmp_path, source='''import p"@lib/std/signals.dewy" as signals
block = (label:string started:Channel<bool> reports:Channel<string>) => {
    let done = channel<bool>(1)
    concurrent {
        spawn {
            _ = signals.sigusr1.next(timeout=0s)
            started.send(true) or_throw
            loop _ in signals.sigusr1 { reports.send(label) or_throw done.send(true) or_throw }
        }
        done.receive or_throw;
    }
}
main = () => {
    let started = channel<bool>(2)
    let reports = channel<string>(2)
    concurrent {
        spawn block("one" started reports)
        spawn block("two" started reports)
        started.receive or_throw;
        started.receive or_throw;
        printl"ready"
        printl(reports.receive or_throw)
        printl(reports.receive or_throw)
    }
    printl"restored"
    sleep(30s) or_throw
}
''')
    child = start(binary)
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGUSR1)
        assert {line(child), line(child)} == {'one\n', 'two\n'}
        assert line(child) == 'restored\n'
        status = Path(f'/proc/{child.pid}/status').read_text()
        caught = int(next(row.split()[1] for row in status.splitlines() if row.startswith('SigCgt:')), 16)
        assert not caught & (1 << (signal.SIGUSR1 - 1))
    finally:
        finish(child)


def test_intercept_and_observe_have_independent_mailboxes(compiler, tmp_path):
    binary = build(compiler, tmp_path, source='''import p"@lib/std/signals.dewy" as signals
main = () => {
    let started = channel<bool>(2)
    let received = channel<bool>(2)
    concurrent {
        spawn {
            _ = signals.ctrl_c.next(timeout=0s)
            started.send(true) or_throw
            loop _ in signals.ctrl_c { printl"intercept" received.send(true) or_throw }
        }
        spawn {
            let passive = signals.ctrl_c.observe
            _ = passive.next(timeout=0s)
            started.send(true) or_throw
            loop _ in passive { printl"observe" received.send(true) or_throw }
        }
        started.receive or_throw;
        started.receive or_throw;
        printl"ready"
        received.receive or_throw;
        received.receive or_throw;
    }
    printl"joined"
}
''')
    child = start(binary)
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGINT)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0, err.decode()
        # Console fragments from independent writers may interleave.
        assert b''.join(out.split()) in (b'observeinterceptjoined', b'interceptobservejoined')
    finally:
        finish(child)


def test_observer_preserves_termination_default(compiler, tmp_path):
    binary = build(compiler, tmp_path, source='''import p"@lib/std/signals.dewy" as signals
main = () => {
    _ = signals.sigterm.observe.next(timeout=0s)
    printl"ready"
    sleep(30s) or_throw
}
''')
    child = start(binary)
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGTERM)
        child.communicate(timeout=10)
        assert child.returncode == -signal.SIGTERM
    finally:
        finish(child)


@pytest.mark.parametrize('release', [False, True])
def test_multiple_native_sources(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, 'signals_multiple/two_sources', release=release)
    child = start(binary, 'live')
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGTERM)
        assert line(child) == 'sigterm\n'
        os.kill(child.pid, signal.SIGUSR1)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0, err.decode()
        assert out == b'sigusr1\njoined\n'
    finally:
        finish(child)


def test_root_listener_stays_open(compiler, tmp_path):
    binary = build(compiler, tmp_path, source='''import p"@lib/std/signals.dewy" as signals
main = () => {
    _ = signals.sigusr1.next(timeout=0s)
    printl"ready"
    let event = signals.sigusr1.next or_throw
    printl(event.name)
    printl"{signals.sigusr1.next(timeout=0s) is? Timeout}"
}
''')
    child = start(binary)
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGUSR1)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0, err.decode()
        assert out == b'sigusr1\ntrue\n'
    finally:
        finish(child)


def test_three_observed_ctrl_c_arrivals_force_exit(compiler, tmp_path):
    import time
    binary = build(compiler, tmp_path, source='''import p"@lib/std/signals.dewy" as signals
main = () => {
    _ = signals.ctrl_c.next(timeout=0s)
    printl"ready"
    loop _ in signals.ctrl_c { printl"press" }
}
''')
    child = start(binary)
    try:
        assert line(child) == 'ready\n'
        began = time.monotonic()
        for _ in range(2):
            os.kill(child.pid, signal.SIGINT)
            assert line(child) == 'press\n'
        if time.monotonic() - began > .8:
            pytest.skip('shared host could not deliver three observed presses in one second')
        os.kill(child.pid, signal.SIGINT)
        child.communicate(timeout=10)
        assert child.returncode == 130
    finally:
        finish(child)


def test_select_preserves_source_provenance(compiler, tmp_path):
    binary = build(compiler, tmp_path, source='''import p"@lib/std/signals.dewy" as signals
watch = (started:Channel<bool> done:Channel<bool>) => {
    let term = signals.sigterm
    let usr = signals.sigusr1
    _ = term.next(timeout=0s)
    _ = usr.next(timeout=0s)
    started.send(true) or_throw
    loop true {
        match select(@term.next @usr.next) {
            _:term.Signal => { printl"term" done.send(true) or_throw }
            _:usr.Signal => { printl"usr" done.send(true) or_throw }
            <Closed> => break
            <Canceled> => Canceled or_throw
        }
    }
}
main = () => {
    let started = channel<bool>(1)
    let done = channel<bool>(2)
    concurrent {
        spawn watch(started done)
        started.receive or_throw;
        printl"ready"
        done.receive or_throw;
        done.receive or_throw;
    }
    printl"joined"
}
''')
    child = start(binary)
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGTERM)
        assert line(child) == 'term\n'
        os.kill(child.pid, signal.SIGUSR1)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0, err.decode()
        assert out == b'usr\njoined\n'
    finally:
        finish(child)


def test_observer_preserves_inherited_ignore(compiler, tmp_path):
    binary = build(compiler, tmp_path, source='''import p"@lib/std/signals.dewy" as signals
main = () => {
    let source = signals.sigterm.observe
    _ = source.next(timeout=0s)
    printl"ready"
    let event = source.next or_throw
    printl(event.name)
}
''')
    # Set the inherited disposition only in our child, then exec the program
    # in that same PID. The desktop session's dispositions are untouched.
    setup = ('import os,signal,sys; signal.signal(signal.SIGTERM,signal.SIG_IGN); '
             'os.execv(sys.argv[1],[sys.argv[1]])')
    child = start(sys.executable, '-c', setup, str(binary))
    try:
        assert line(child) == 'ready\n'
        os.kill(child.pid, signal.SIGTERM)
        out, err = child.communicate(timeout=10)
        assert child.returncode == 0, err.decode()
        assert out == b'sigterm\n'
    finally:
        finish(child)
