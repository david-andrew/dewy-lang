"""Library proof transfers agree with the frozen compiler leaves."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def paths(*names):
    return [str(ROOT / 'tests/cases' / (name + '.dewy')) for name in names]


def test_coverlib_facts_forks_twins(compiler, tmp_path, monkeypatch):
    result = compare_builds(compiler, tmp_path, monkeypatch, ('facts_forks',), paths(
        'coverlib/array_rank_lookup', 'coverlib_proofs/map_foreign_positions',
        'coverlib_proofs/map_changed_capture'), flags=((), ('--release',)))
    assert all(row[2] == 0 for row in result[:2])
    assert all(row[2] != 0 for row in result[2:])


def test_coverlib_facts_maps_twins(compiler, tmp_path, monkeypatch):
    result = compare_builds(compiler, tmp_path, monkeypatch, ('facts_maps',), paths(
        'coverlib/set_pending_queue', 'coverlib/dict_tombstone_report',
        'coverlib_proofs/store_removed_empty', 'coverlib_proofs/set_missing_member'),
        flags=((), ('--release',)))
    assert all(row[2] == 0 for row in result[:4])
    assert all(row[2] != 0 for row in result[4:])


def test_coverlib_facts_changes_twins(compiler, tmp_path, monkeypatch):
    result = compare_builds(compiler, tmp_path, monkeypatch, ('facts_changes',), paths(
        'coverlib/array_rotate_window', 'coverlib_proofs/rotate_invalid_index',
        'coverlib_proofs/rotate_index_effect'), flags=((), ('--release',)))
    assert all(row[2] == 0 for row in result[:2])
    assert all(row[2] != 0 for row in result[2:])


def test_coverlib_checks_hints_twins(compiler, tmp_path, monkeypatch):
    wrong = tmp_path / 'wrong_optional_receiver.dewy'
    wrong.write_text('label=(s:string?):>string=>s ?? "empty"\n'
                     'main=()=>{let n=42; printl(n.label)}\n')
    result = compare_builds(compiler, tmp_path, monkeypatch, ('checks_hints',),
                            paths('coverlib/json_dynamic_logs') + [str(wrong)],
                            flags=((), ('--release',)))
    assert all(row[2] == 0 for row in result[:2])
    assert all(row[2] != 0 for row in result[2:])
