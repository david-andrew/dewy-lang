"""Argument declaration order and unscoped control joins match the frozen leaves."""
import pytest
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def cases(prefixes):
    return sorted(str(p.relative_to(ROOT)) for p in
                  (ROOT / 'tests/cases/coverweek2').glob('*.dewy')
                  if any(p.name.startswith(prefix) for prefix in prefixes))


def test_coverweek2_scope_joins_conditionals_match_vardecls_definite_twins(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch,
                   ('scope_joins', 'checker_conditionals', 'checker_match',
                    'checker_vardecls', 'checker_hooks', 'checker_loops', 'definite_walk'),
                   cases(('if_', 'iflet_', 'match_', 'loop_')),
                   flags=((), ('--release',)))


def test_coverweek2_ownership_checks_lower_group_twins(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch,
                   ('ownership_checks', 'lower_group'),
                   cases(('if_owner', 'call_', 'if_shadow')),
                   flags=((), ('--release',)))


def test_coverweek2_checker_expr_value_calls_twins(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch,
                   ('checker_value_calls', 'checker_expr', 'checker_call_services'), cases(('call_',)),
                   flags=((), ('--release',)))


@pytest.mark.parametrize("release", [False, True], ids=["default", "release"])
def test_coverweek2_dewy_reader_twins(compiler, tmp_path, release):
    from tools.compiler import parser_diff
    pair = parser_diff.build_pair(compiler, tmp_path, release=release)
    failures = parser_diff.compare(pair, [ROOT / p for p in cases(('call_', 'if_', 'match_', 'loop_'))],
                                   tmp_path, release=release, workers=1)
    assert not failures, failures
