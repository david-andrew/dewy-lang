"""Exercise the file driver's declarations and diagnostics on pinned inputs."""

import subprocess

import pytest

from tests.corpus_cache import CORPUS, built_once
from tests.support import compiler  # noqa: F401
from tests import parser_oracle
from tools.compiler import parser_diff

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_file_driver_corpus(compiler, tmp_path, release):
    pair = built_once(('reader', compiler, release), lambda work: parser_oracle.build_pair(compiler, work, release))
    directories = ('target', 'testing', 'misc', 'witness', 'directives', 'ffi',
                   'overload', 'constant', 'frontend', 'truncated')
    sources = sorted(p for directory in directories
                     for p in (CORPUS / directory).glob('*.dewy'))
    assert sources
    sources += parser_diff.generated(tmp_path / 'generated', 4)
    failures = parser_oracle.compare(pair, sources, tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)


def test_parse_live_compiler_sources(compiler, tmp_path):
    sources = sorted((parser_diff.ROOT / 'compiler').glob('*.dewy'))
    assert sources
    # A single module loads every compiler source through the regular parser.
    entry = tmp_path / 'live.jo'
    entry.write_text(''.join(f'use {str(path)!r}\n' for path in sources))
    env = {**parser_diff.environment(parser_diff.ROOT / 'lib'), 'DEWY_STOP': 'parse'}
    run = subprocess.run([compiler, 'check', entry], capture_output=True, timeout=60, env=env)
    assert run.returncode == 0, run.stdout + run.stderr


def test_file_driver_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_file.dewy\0' in binary
    assert b'/compiler/dewy_file.jo\0' not in binary
