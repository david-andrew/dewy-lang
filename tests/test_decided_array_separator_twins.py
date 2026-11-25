"""Batch-6 scalar separators and context-based discard agree with the frozen readers.

D39 nesting and comprehensions retain their existing behavior. The literal-only
migrations in ir_operands, lower_determinism, targets and unit_rare are included
in the differential compiler build, alongside expr_rare's scalar/row dispatch.
"""
import pytest

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
from tests import parser_oracle

pytestmark = pytest.mark.nightly

CASES = sorted((ROOT / 'tests/cases/decided_array_separators').glob('*.dewy'))


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_decided_array_dewy_reader(compiler, tmp_path, release):
    pair = parser_oracle.build_pair(compiler, tmp_path, release)
    failures = parser_oracle.compare(pair, CASES, tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)


def test_decided_array_leaves(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch,
                   ('checks_value_hooks', 'checker_call_convert', 'literal_snapshots', 'checker_blocks', 'dewy_scan', 'expr_rare', 'ir_operands', 'lower_determinism', 'targets', 'unit_rare', 'utf8_text', 'sha', 'lsp_fixes', 'dewy_lex'),
                   CASES, flags=((), ('--release',)))
