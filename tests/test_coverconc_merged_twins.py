"""Nested receives and optional outcome members agree with their frozen twins."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_merged_waits_twins(compiler, tmp_path, monkeypatch):
    paths = [str(p.relative_to(ROOT)) for p in
             sorted((ROOT / 'tests/cases/coverconc_merged').glob('*.dewy'))]
    result = compare_builds(compiler, tmp_path, monkeypatch,
                           ('merged_checks', 'checker_call_services', 'partial_checks',
                            'type_member_checks'), paths,
                           flags=((), ('--release',)))
    assert result and all(row[2] == 0 for row in result)
