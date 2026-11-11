"""Prepared-place and terminal-progress rules agree with frozen twins."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_prepared_select_twins(compiler, tmp_path, monkeypatch):
    directories = ('coverconc_spin', 'coverconc_provenance',
                   'coverconc_field_waits', 'coverconc_channel_payloads')
    paths = [str(p.relative_to(ROOT)) for directory in directories
             for p in sorted((ROOT / 'tests/cases' / directory).glob('*.dewy'))]
    results = compare_builds(compiler, tmp_path, monkeypatch,
                            ('select_checks', 'select_progress_checks',
                             'checks_place_updates'), paths,
                            flags=((), ('--release',)))
    assert sum(row[2] == 0 for row in results) >= 10
    assert sum(row[2] != 0 for row in results) >= 10
