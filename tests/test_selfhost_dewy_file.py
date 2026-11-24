"""The Dewy file driver and frozen twin preserve declarations and first errors."""

import pytest

from tests.corpus_cache import corpus_under
from tests.support import compiler  # noqa: F401
from tests import parser_oracle
from tools.compiler import parser_diff


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_file_driver_matches_frozen(compiler, tmp_path, release):
    pair = parser_oracle.build_pair(compiler, tmp_path, release)
    cases = parser_diff.ROOT / 'tests/cases'
    directories = ('target', 'testing', 'misc', 'witness', 'directives', 'ffi',
                   'overload', 'constant', 'frontend', 'truncated')
    assert all((cases / directory).is_dir() for directory in directories)
    sources = sorted(p for directory in directories
                     for p in corpus_under(cases / directory, recursive=False))
    sources += parser_diff.generated(tmp_path / 'generated', 4)
    failures = parser_oracle.compare(pair, sources, tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)
    shared = tmp_path / 'shared-panics'
    assert not shared.exists(), shared.read_text()


def test_file_driver_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_file.dewy\0' in binary
    assert b'/compiler/dewy_file.jo\0' not in binary
