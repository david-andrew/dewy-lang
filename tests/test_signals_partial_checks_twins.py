"""Generic prepared source methods have the same provenance with frozen twins."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_signals_partial_checks(compiler, tmp_path, monkeypatch):
    ordinary = tmp_path / 'ordinary_iterator.dewy'
    ordinary.write_text("""Cursor:type=[n:int64 next=():>int64=>n]
main=()=>{let cursor=Cursor[1] select(@cursor.next);}
""")
    results = compare_builds(compiler, tmp_path, monkeypatch, ('partial_checks',), [
        'tests/cases/signals_closing/select.dewy',
        'tests/cases/signals_closing/merged.dewy',
        'tests/cases/reserve/select.dewy',
        'tests/cases/reserve/channel_select.dewy',
        'ordinary_iterator.dewy',
    ], flags=((), ('--release',)))
    assert all(row[2] == 0 for row in results if not row[0].endswith('ordinary_iterator.dewy'))
    assert all(row[2] != 0 and 'select waits on operations' in row[4]
               for row in results if row[0].endswith('ordinary_iterator.dewy'))
