"""Record programs that fail to compile, for working on the compiler.

While the tokenizer, parser, or checker are being developed, every `dewy
file.dewy`, `dewy test file.dewy`, and `dewy analyze file.dewy` whose
compile fails writes one human-readable markdown file: the command, the
error (the report, or the traceback of an internal crash), and every source
the compile read, inlined (library files are only listed by path). The files
are meant to be pruned by hand afterwards, keeping the cases worth turning
into compiler adjustments.

Turning it on is a one-time step: `mkdir ~/.dewy/failures`. Recording
happens whenever that directory exists (rename or remove it to stop).
`DEWY_FAILURE_LOG=<dir>` records somewhere else instead, and
`DEWY_FAILURE_LOG=0` turns recording off. Nothing is recorded under pytest
unless `DEWY_FAILURE_LOG` names a directory: the suite compiles failing
programs on purpose.
"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import reporting
from .reporting import ReportException, SrcFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIBRARY = PROJECT_ROOT / 'library'
DEFAULT_DIRECTORY = Path.home() / '.dewy' / 'failures'


def directory() -> Path | None:
    """Where failures are recorded, or `None` when recording is off."""
    override = os.environ.get('DEWY_FAILURE_LOG')
    if override is not None:
        return None if override.strip() in ('', '0') else Path(override).expanduser()
    if 'PYTEST_VERSION' in os.environ:
        return None
    return DEFAULT_DIRECTORY if DEFAULT_DIRECTORY.is_dir() else None


class _Recorder:
    def __init__(self, command: list[str]) -> None:
        self.command = command
        self.sources: list[SrcFile] = []

    def read(self, srcfile: SrcFile) -> None:
        self.sources.append(srcfile)

    def record(self, error: str, *, notes: Sequence[str] = ()) -> Path | None:
        target = directory()
        if target is None or not self.sources:
            return None
        try:
            target.mkdir(parents=True, exist_ok=True)
            path = _fresh_path(target, self.sources[0])
            path.write_text(self.render(error, notes))
        except OSError:
            return None
        return path

    def render(self, error: str, notes: Sequence[str]) -> str:
        entry = self.sources[0]
        lines = [
            f'# compile failure: {entry.path.name if entry.path else "<memory>"}',
            '',
            f'- when: {datetime.now():%Y-%m-%d %H:%M:%S}',
            f'- command: `{" ".join(self.command)}`',
            f'- cwd: `{Path.cwd()}`',
            f'- compiler: dewy {_version()} ({_git_revision()})',
            *(f'- {note}' for note in notes),
            '',
            '## error',
            '',
            _fenced(error, 'text'),
            '',
            '## sources',
            '',
        ]
        library: list[Path] = []
        seen: set[Path] = set()
        for srcfile in self.sources:
            path = Path(srcfile.path).resolve() if srcfile.path else None
            if path is not None:
                if path in seen:
                    continue
                seen.add(path)
                if path.is_relative_to(LIBRARY):
                    library.append(path)
                    continue
            lines += [f'### {path or "<memory>"}', '', _fenced(srcfile.body, 'dewy'), '']
        if library:
            lines += ['### library', '', *(f'- {path}' for path in library), '']
        return '\n'.join(lines)


def _fenced(text: str, language: str) -> str:
    fence = '`' * max(3, *(len(run) + 1 for run in _backtick_runs(text)))
    return f'{fence}{language}\n{text.rstrip()}\n{fence}'


def _backtick_runs(text: str) -> Iterator[str]:
    yield ''
    run = ''
    for char in text:
        if char == '`':
            run += char
        elif run:
            yield run
            run = ''
    if run:
        yield run


def _fresh_path(target: Path, entry: SrcFile) -> Path:
    stem = Path(entry.path).stem if entry.path else 'memory'
    base = f'{datetime.now():%Y%m%d-%H%M%S}-{stem}'
    path = target / f'{base}.md'
    count = 1
    while path.exists():
        count += 1
        path = target / f'{base}-{count}.md'
    return path


def _version() -> str:
    try:
        return (PROJECT_ROOT / 'VERSION').read_text().strip()
    except OSError:
        return 'unknown'


def _git_revision() -> str:
    try:
        done = subprocess.run(['git', '-C', str(PROJECT_ROOT), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, check=False, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return 'no git'
    return done.stdout.strip() if done.returncode == 0 else 'no git'


def error_text(error: BaseException) -> str:
    if isinstance(error, ReportException):
        error.report.use_color = False
        return str(error.report)
    return ''.join(traceback.format_exception(error))


@contextmanager
def recording(command: list[str]) -> Iterator[_Recorder]:
    """Record the sources read inside the block; an exception leaving it is written up as a failure.

    The block's own handlers can also call `recorder.record(text)` for a
    failure they report themselves (the µDewy stage rejecting the output).
    """
    recorder = _Recorder(command)
    if directory() is None:
        yield recorder
        return
    reporting.source_readers.append(recorder.read)
    try:
        yield recorder
    except Exception as error:
        path = recorder.record(error_text(error))
        if path is not None:
            print(f'(failure recorded at {path})', file=sys.stderr)
        raise
    finally:
        reporting.source_readers.remove(recorder.read)
