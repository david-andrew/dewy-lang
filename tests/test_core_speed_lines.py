"""`build --time` counts the lines of exactly the files the compile loaded, each once."""
import subprocess
from pathlib import Path

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tools.compiler import speed_corpus as corpus

PLAIN = 'printl"hello"\n'
WITH_FMT = "let x=3.14159\nprintl\"{fmt'.2f'(x)}\"\n"
FMT_FILES = {'prelude/formats.dewy', 'bigint.dewy', 'rational.dewy'}


def needs_counters(time_stderr):
    """build --time reports nodes and lines only with hardware counters, which CI's virtual machines lack."""
    if corpus.node_total(time_stderr) is None:
        pytest.skip('no hardware counters on this host: build --time counts nothing')


def counted(compiler, tmp_path, name, text):
    program = tmp_path / f'{name}.dewy'
    program.write_text(text)
    run = subprocess.run([compiler, 'build', program, '--time', '-o', tmp_path / name], capture_output=True, text=True,
                         timeout=120, env={'PATH': '/usr/bin:/bin', 'DEWY_CORE_LIB': str(ROOT / 'lib')})
    assert run.returncode == 0, run.stdout + run.stderr
    needs_counters(run.stderr)
    rows = corpus.counted_sources(run.stderr)
    found = corpus.processed(run.stderr)
    assert found is not None
    return program, rows, found


@pytest.mark.parametrize('name, text, uses_fmt', [('plain', PLAIN, False), ('fmt', WITH_FMT, True)])
def test_counted_files_are_the_loaded_files(compiler, tmp_path, name, text, uses_fmt):
    program, rows, found = counted(compiler, tmp_path, name, text)
    root = [Path(path) for side, _, path in rows if side == 'root']
    library = {Path(path): lines for side, lines, path in rows if side == 'library'}
    # the program's files: the entry and what it imports, each once
    assert [p.resolve() for p in root] == corpus.root_files(program)
    assert sum(lines for side, lines, _ in rows if side == 'root') == found['root']
    # the library files: those under lib/, each counted for at most what it holds, never below nothing
    assert len(library) == sum(side == 'library' for side, _, _ in rows)
    for path, lines in library.items():
        assert path.is_relative_to(ROOT / 'lib'), path
        assert 0 <= lines <= corpus.source_lines(path.read_text()), path
    assert sum(library.values()) == found['library'] >= 0
    # the fmt library loads only for a program that uses fmt
    names = {str(path.relative_to(ROOT / 'lib')) for path in library}
    assert FMT_FILES <= names if uses_fmt else not FMT_FILES & names
    assert found['all'] == found['root'] + found['library'] + found['instance'] > 0


@pytest.mark.parametrize('entry', ['97_notes_service/design.dewy', '101_ml_training/core.dewy', '95_kv_store/design.dewy'])
def test_flagship_lines_are_never_negative(compiler, tmp_path, entry):
    program = ROOT / 'tests/ladder' / entry
    run = subprocess.run([compiler, 'build', program, '--time', '-o', tmp_path / 'program'], capture_output=True, text=True,
                         timeout=300, env={'PATH': '/usr/bin:/bin', 'DEWY_CORE_LIB': str(ROOT / 'lib')})
    assert run.returncode == 0, run.stdout + run.stderr
    needs_counters(run.stderr)
    found = corpus.processed(run.stderr)     # raises on a negative or inconsistent count
    assert found is not None and found['library'] > 0 and found['all'] > found['root']
    assert all(lines >= 0 for _, lines, _ in corpus.counted_sources(run.stderr))
