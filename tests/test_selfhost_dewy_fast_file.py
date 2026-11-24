"""The Dewy frontend file services and their frozen Jo twin emit the same bytes."""

import pytest

from tests.support import compiler  # noqa: F401
from tests import parser_oracle
from tools.compiler import parser_diff


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_fast_file_matches_twin(compiler, tmp_path, release):
    pair = parser_oracle.build_pair(compiler, tmp_path, release)
    names = (
        'constant/shadowable_let',
        'constant/shadowable_function_assign',
        'directives/scope_module',
        'directives/no_nan_proven',
        'errors/proofs_after_unrelated_error',
        'frontend/declarations_direct_declarations_1',
        'testing/test_block_form',
    )
    cases = parser_diff.ROOT / 'tests/cases'
    sources = [cases / f'{name}.dewy' for name in names]
    assert all(path.is_file() for path in sources)
    failures = parser_oracle.compare(pair, sources, tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)


def test_fast_file_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_fast_file.dewy\0' in binary
    assert b'/compiler/dewy_fast_file.jo\0' not in binary
