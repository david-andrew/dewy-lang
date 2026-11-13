"""Unscoped `( ... )` blocks, `f{...}` calls and parallel blocks match their frozen leaves:
dewy_reader against its seed, and the checker, lowering, fact and hint leaves."""
import pytest

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
from tools.compiler import parser_diff

CASES = sorted(str(p.relative_to(parser_diff.ROOT)) for folder in ('block_scope', 'parallel_blocks')
               for p in (parser_diff.ROOT / 'tests/cases' / folder).glob('*.dewy'))


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_blockscope_dewy_reader(compiler, tmp_path, release):
    pair = parser_diff.build_pair(compiler, tmp_path, release)
    failures = parser_diff.compare(pair, [parser_diff.ROOT / p for p in CASES], tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)


def test_blockscope_leaves(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch,
                   ('checker_blocks', 'lower_group', 'facts_forgets', 'checks_hints'),
                   CASES, flags=((), ('--release',)))
