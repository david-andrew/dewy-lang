"""Run the compiler's processes (a file watch with edits and restarts, the interactive prompt, fused
and parallel builds) with a compiler made with Dewy leaves and with one made with their frozen
twins: the same transcripts, exit codes and files.

Every process a session starts is in its own session (process group) and is ended by the
session: only that group is ever signalled."""
import contextlib
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time

from tests.selfhost_build_double import build_all
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, patience
from tests.test_core_watch import save

LIB = {'DEWY_CORE_LIB': str(ROOT / 'lib')}


def _env(extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(LIB, DEWY_NO_AUDIO='1', DISPLAY='', WAYLAND_DISPLAY='', **(extra or {}))
    return env


def _compilers(compiler, tmp_path, monkeypatch, leaves):
    monkeypatch.setenv('DEWY_CORE_LIB', LIB['DEWY_CORE_LIB'])
    return leaf_compilers(compiler, tmp_path, leaves)


class Session:
    """One watched program: its two output streams, read as they come."""

    def __init__(self, binary, source, options, game):
        extra = {'DEWY_SOFTWARE': '1', 'DEWY_FRAMES': '1000000', 'DEWY_EMIT_WORKERS': '1',
                 'DEWY_WATCH_LOG': '1'}
        if game:
            extra['DEWY_SCREENSHOT'] = str(source.parent / 'unused.png')
        self.process = subprocess.Popen([binary, *options, source], cwd=source.parent, env=_env(extra),
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True)
        self.streams = {'out': b'', 'err': b''}
        self.seen = 0
        self.chunks = queue.Queue()
        self.readers = [threading.Thread(target=self.read, args=(name, pipe), daemon=True)
                        for name, pipe in (('out', self.process.stdout), ('err', self.process.stderr))]
        for reader in self.readers:
            reader.start()

    def read(self, name, pipe):
        with contextlib.suppress(OSError):
            while data := pipe.read1(16384):
                self.chunks.put((name, data))
        self.chunks.put((name, b''))

    def text(self):
        return (self.streams['out'] + self.streams['err']).decode(errors='replace')

    def expect(self, pattern, timeout=30):
        """Wait until pattern appears in either stream after the previous match."""
        end = time.monotonic() + patience(timeout)
        while True:
            # (each stream is searched from where the last match left off in it)
            for name in ('out', 'err'):
                found = re.search(pattern, self.streams[name].decode(errors='replace')[self.marks[name]:])
                if found:
                    self.marks[name] += found.end()
                    return
            remaining = end - time.monotonic()
            assert remaining > 0, f'expected {pattern!r}:\n{self.text()}'
            try:
                name, data = self.chunks.get(timeout=remaining)
            except queue.Empty:
                raise AssertionError(f'expected {pattern!r}:\n{self.text()}') from None
            self.streams[name] += data

    def close(self):
        """Quit the watch (q + enter), or end its whole process group; the exit code."""
        try:
            if self.process.poll() is None:
                with contextlib.suppress(OSError):
                    self.process.stdin.write(b'q\n')
                    self.process.stdin.flush()
            self.process.wait(timeout=patience(10))
        except subprocess.TimeoutExpired:
            pass
        finally:
            # (the watch's builds and the program it runs are in the group this session made)
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=10)
            with contextlib.suppress(OSError):
                self.process.stdin.close()
            for reader in self.readers:
                reader.join(timeout=5)
            while not self.chunks.empty():
                name, data = self.chunks.get()
                self.streams[name] += data
        return self.process.returncode


def normalize(data, binary, directory):
    """A stream's lines without timings, process ids, the session's directory or repeated frames:
    consecutive equal lines collapse, and of the watch log only the patch sizes stay."""
    lines = []
    text = data.decode(errors='replace').replace(str(binary), 'dewy-core').replace(str(directory), '<dir>')
    for line in text.splitlines():
        if line.startswith('dewy-core watch log: '):
            if 'sending a patch' not in line:
                continue
        line = re.sub(r'\d+ ms\b', 'N ms', line)
        if not lines or lines[-1] != line:
            lines.append(line)
    return lines


def watch_session(binary, directory, files, steps, options=('watch',), game=False):
    """files: {name: text}, the first one watched; steps: ('save', name, text), ('expect', regex),
    ('key', text typed). The normalized streams, the exit code and the files left behind."""
    directory.mkdir()
    for name, text in files.items():
        save(directory / name, text)
    marks = {'out': 0, 'err': 0}
    session = Session(binary, directory / next(iter(files)), options, game)
    session.marks = marks
    try:
        for step in steps:
            if step[0] == 'save':
                save(directory / step[1], step[2])
            elif step[0] == 'key':
                session.process.stdin.write(step[1].encode())
                session.process.stdin.flush()
            else:
                session.expect(step[1])
    finally:
        code = session.close()
    left = {p.name: p.read_bytes() for p in sorted(directory.iterdir())
            if p.is_file() and p.name not in files and not p.name.startswith('.') and p.suffix != '.png'}
    return (normalize(session.streams['out'], binary, directory), normalize(session.streams['err'], binary, directory), code,
            sorted(left))


def compare_watch(compiler, tmp_path, monkeypatch, leaves, files, steps, **options):
    dewy, jo = _compilers(compiler, tmp_path, monkeypatch, leaves)
    expected = watch_session(jo, tmp_path / 'jo', files, steps, **options)
    got = watch_session(dewy, tmp_path / 'dewy', files, steps, **options)
    assert got == expected, (got, expected)
    return expected


def _type_lines(process, master, data, deadline):
    """Type data one line at a time, each after the prompt has drawn again; what the prompt wrote meanwhile."""
    import select
    prompt = re.compile(rb'\r\n[\s\S]*(?:>>> |\.\.\. )')
    fd = process.stdout.fileno()
    seen = b''

    def wait(pattern, start):
        nonlocal seen
        while not pattern.search(seen, start):
            ready, _, _ = select.select([fd], [], [], max(deadline - time.monotonic(), 0))
            if not ready:
                raise subprocess.TimeoutExpired(process.args, 0)
            chunk = os.read(fd, 65536)
            if not chunk:
                return False
            seen += chunk
        return True

    alive = wait(re.compile(rb'>>> '), 0)
    for line in re.findall(rb'[^\n]*\n|[^\n]+', data):
        if not alive:
            break
        start = len(seen)
        with contextlib.suppress(OSError):
            os.write(master, line)
        alive = wait(prompt, start)
    return seen


def run_prompt(binary, text, directory, timeout, paced=False):
    """Feed text (or bytes) to the prompt through a pseudo-terminal (as tests/repl_pty.py does); its whole
    process group ends with it."""
    import pty
    from tests.repl_pty import ANSI, BANNER, REDRAW
    master, slave = pty.openpty()
    env = _env({'DEWY_EMIT_WORKERS': '1', 'DEWY_REPL_HISTORY': str(directory / 'repl-history'),
                'TMPDIR': str(directory)})
    process = subprocess.Popen([binary], cwd=directory, env=env, stdin=slave, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    os.close(slave)

    def drain():  # (the terminal's echo of what is typed ahead must not fill its buffer)
        with contextlib.suppress(OSError):
            while os.read(master, 4096):
                pass

    threading.Thread(target=drain, daemon=True).start()
    ahead = b''
    try:
        data = text if isinstance(text, bytes) else text.encode()
        if paced:  # (the terminal is raw only while a line is read: keys wait for each prompt, as a typist's do)
            ahead = _type_lines(process, master, data, time.monotonic() + timeout)
        else:
            os.write(master, data)
        out, err = process.communicate(timeout=timeout)
        out = ahead + out
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        os.close(master)
    out = REDRAW.sub(b'', ANSI.sub(b'', out)).replace(BANNER, b'', 1).replace(b'\r', b'')
    return process.returncode, out.decode(errors='replace'), err.decode(errors='replace')


def compare_repl(compiler, tmp_path, monkeypatch, leaves, transcripts, paced=False):
    """transcripts: texts typed at the prompt, each a fresh prompt; stdout, stderr and exit codes."""
    dewy, jo = _compilers(compiler, tmp_path, monkeypatch, leaves)
    results = []
    for label, binary in (('jo', jo), ('dewy', dewy)):
        runs = []
        for i, text in enumerate(transcripts):
            directory = tmp_path / f'{label}{i}'
            directory.mkdir()
            code, out, err = run_prompt(binary, text, directory, patience(60), paced)
            history = directory / 'repl-history'
            runs.append((code, out.replace(str(binary), 'dewy-core'), err.replace(str(binary), 'dewy-core'),
                         history.read_bytes() if history.exists() else b''))
        results.append(runs)
    assert results[1] == results[0]
    return results[0]


def compare_workers(compiler, tmp_path, monkeypatch, leaves, paths, workers=(2, 4), extra=None):
    """Build each path with fused and parallel workers (forced even for a small program): the same
    exit codes, messages and bytes, which also match one process. The timed report of the leaf
    build: what ran."""
    dewy, jo = _compilers(compiler, tmp_path, monkeypatch, leaves)
    paths = [p if (tmp_path / p).exists() else ROOT / p for p in paths]
    serial = None
    for n in (1, *workers):
        settings = {'DEWY_EMIT_WORKERS': str(n), 'DEWY_EMIT_FORCE': '1', **(extra or {})}
        with monkeypatch.context() as m:
            for key, value in settings.items():
                m.setenv(key, value)
            expected = build_all(jo, tmp_path, f'jo{n}', paths)
            got = build_all(dewy, tmp_path, f'dewy{n}', paths)
        for a, b in zip(got, expected):
            assert a[2:5] == b[2:5] and list(a[5].values()) == list(b[5].values()), (a[0], n, a[2:5], b[2:5])
        if serial is None:
            serial = expected
        for a, b in zip(expected, serial):
            assert a[2:5] == b[2:5] and list(a[5].values()) == list(b[5].values()), (a[0], n)
    reports = []
    for path in paths:
        out = tmp_path / 'timed'
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir()
        run = subprocess.run([dewy, 'build', path, '-o', out / 'p'], cwd=tmp_path, capture_output=True,
                             text=True, timeout=120, check=False,
                             env=_env({'DEWY_EMIT_WORKERS': str(workers[-1]), 'DEWY_EMIT_FORCE': '1',
                                       'DEWY_PAR_TIME': '1', **(extra or {})}))
        reports.append(run.stderr)
    return reports
