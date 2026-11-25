"""Direct reader services match their frozen Jo twin in both build modes."""

import pytest

from tests.support import compiler  # noqa: F401
from tests import parser_oracle
from tools.compiler import parser_diff

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_dewy_direct_ops_matches_twin(compiler, tmp_path, release):
    pair = parser_oracle.build_pair(compiler, tmp_path, release)
    names = (
        'facts/long_body',
        'loop/block_without_body',
        'coalesce/lazy_order',
        'ladder_diagnostics/report_pipeline',
        'frontend/declarations_direct_declarations_1',
        'witness/proof_body',
        'directives/scope_module',
    )
    cases = parser_diff.ROOT / 'tests/cases'
    sources = [cases / f'{name}.dewy' for name in names]
    assert all(path.is_file() for path in sources)
    failures = parser_oracle.compare(pair, sources, tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)


def test_dewy_direct_ops_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_direct_ops.dewy\0' in binary
    assert b'/compiler/dewy_direct_ops.jo\0' not in binary
