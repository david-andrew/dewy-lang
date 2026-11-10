"""The compile-speed gate's source drift column: a program whose own files changed since the base is compiled by
both compilers on this source, so only measuring the candidate on the base's copy shows the source's own growth."""
import pytest

from tools.compiler import speed


def drift(role='base', old=100_000_000, new=121_000_000, same=100_500_000, name='flagship 95_sql_engine'):
    return speed.Drift(role, name, 'c17f785a1c', old, new, same)


def test_drift_splits_compiler_alone_from_source_alone():
    d = drift()
    assert d.compiler == pytest.approx(21.0)
    assert d.growth == pytest.approx(20.40)
    text = '\n'.join(d.lines())
    assert 'SOURCE DRIFT' in text and '(source alone)' in text and '(compiler alone, the row above)' in text
    assert '0.1005 G' in text and '0.1210 G' in text and '0.1000 G' in text
    assert 'no split' in '\n'.join(drift(same=None).lines())


def test_grown_source_fails_unless_an_accept_line_names_the_program():
    d = drift()
    failures, accepted = speed.drift_verdict([d], 1.0, {'base': []})
    assert len(failures) == 1 and not accepted
    assert 'flagship 95_sql_engine' in failures[0] and '+20.40%' in failures[0]
    assert '0.1005 G old source -> 0.1210 G this source' in failures[0]
    # an accept line that names another program, or none, waives nothing
    for reasons in (['98 grew with its new tests'], ['bigger inlining budget']):
        assert speed.drift_verdict([d], 1.0, {'base': reasons})[0]
    for reasons in (['95 grew a query planner'], ['95_sql_engine adds joins']):
        failures, accepted = speed.drift_verdict([d], 1.0, {'base': reasons})
        assert not failures and len(accepted) == 1 and reasons[0] in accepted[0]


def test_source_within_the_limit_or_shrunk_needs_no_accept_line():
    assert speed.drift_verdict([drift(same=120_500_000)], 1.0, {}) == ([], [])
    assert speed.drift_verdict([drift(same=130_000_000)], 1.0, {}) == ([], [])


def test_unsplit_drift_is_unknown_and_fails():
    failures, _ = speed.drift_verdict([drift(same=None)], 1.0, {'base': []})
    assert len(failures) == 1 and 'growth is unknown' in failures[0]


def test_checkpoint_drift_reads_the_checkpoints_accept_lines_only():
    d = drift(role='checkpoint')
    assert speed.drift_verdict([d], 1.0, {'base': ['95 grew'], 'checkpoint': []})[0]
    assert not speed.drift_verdict([d], 1.0, {'base': [], 'checkpoint': ['95 grew']})[0]


def make(root, files):
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)


def test_only_programs_whose_files_changed_count_as_drifted(monkeypatch, tmp_path):
    here, there = tmp_path / 'here', tmp_path / 'there'
    program = 'tests/ladder/95_sql_engine/core.dewy'
    monkeypatch.setattr(speed, 'ROOT', here)
    same = {program: 'import p"store.dewy"\n', 'tests/ladder/95_sql_engine/store.dewy': 'a\n',
            'tests/ladder/96_other/core.dewy': 'x\n', 'compiler/main.jo': 'old\n'}
    make(here, same)
    make(there, same)
    assert not speed.source_drifted(there, program)
    # a change in an imported file counts; an unrelated program's change does not
    make(here, {'tests/ladder/96_other/core.dewy': 'y\n'})
    assert not speed.source_drifted(there, program)
    assert speed.source_drifted(there, 'tests/ladder/96_other/core.dewy')
    make(here, {'tests/ladder/95_sql_engine/store.dewy': 'a, grown\n'})
    assert speed.source_drifted(there, program)
    # no reference checkout, generated programs, the compiler itself, and programs the reference lacks
    assert not speed.source_drifted(None, program)
    assert not speed.source_drifted(there, str(tmp_path / 'synthetic.dewy'))
    make(here, {'compiler/main.jo': 'new\n'})
    assert not speed.source_drifted(there, 'compiler/main.jo')
    make(here, {'tests/ladder/99_new/core.dewy': 'z\n'})
    assert not speed.source_drifted(there, 'tests/ladder/99_new/core.dewy')
