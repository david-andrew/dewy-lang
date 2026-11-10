"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

PATHS = ('tests/cases/race_sources/inbox.dewy', 'tests/cases/singleton/string_unions.dewy', 'tests/cases/optional/union_member_narrowing.dewy', 'tests/cases/optional/union_else_narrowing_path.dewy')


def test_narrowing_checks_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('narrowing_checks',), PATHS)
