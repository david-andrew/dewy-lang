"""Partial compiler output must not count as a successful copy inventory."""
from subprocess import CompletedProcess

from tools import copy_report


def test_failed_analysis_with_copy_notes(monkeypatch, capsys):
    note = 'copy: source.dewy:1: record copied when binding: source may change\n'
    monkeypatch.setattr(copy_report.subprocess, 'run', lambda *args, **kwargs:
                        CompletedProcess(args, 1, note, 'analysis failed\n'))
    assert copy_report.main(['source.dewy']) == 1
    output = capsys.readouterr()
    assert output.out == ''
    assert output.err == note + 'analysis failed\n'


def test_quoted_compiler_command(monkeypatch, capsys):
    def run(command, **kwargs):
        assert command == ['/compiler directory/dewy', '--debug', 'analyze', 'source.dewy']
        return CompletedProcess(command, 0, 'copy report: 0 record, 0 array and 0 cell copies; 0 string copies\n', '')
    monkeypatch.setattr(copy_report.subprocess, 'run', run)
    assert copy_report.main(['--compiler', '"/compiler directory/dewy" --debug', 'source.dewy']) == 0
    assert capsys.readouterr().out.startswith('0 copies:')


def test_budget_checks_complete_inventory_before_filtering(monkeypatch, capsys):
    report = ('copy: source.dewy:1: array copied when binding: source may change\n'
              'copy: library.dewy:2: string copied when return: caller owns result\n'
              'copy report: 0 record, 1 array and 0 cell copies; 1 string copies\n')
    monkeypatch.setattr(copy_report.subprocess, 'run', lambda *args, **kwargs: CompletedProcess(args, 0, report, ''))
    assert copy_report.main(['source.dewy', '--max-copies', '1']) == 1
    assert '2 sites > 1' in capsys.readouterr().err
    assert copy_report.main(['source.dewy', '--only', 'source.dewy', '--max-copies', '1', '--json']) == 0
    import json
    data = json.loads(capsys.readouterr().out)
    assert data['count'] == 1 and data['within_budget']
    assert data['notes'][0]['kind'] == 'array'
    # A filtered-away missing entry must not pass the gate either.
    report = report.replace('copy: library.dewy:2: string copied when return: caller owns result\n', '')
    assert copy_report.main(['source.dewy', '--only', 'source.dewy', '--max-copies', '1']) == 1
    assert 'incomplete' in capsys.readouterr().err


def test_missing_or_malformed_inventory_fails_closed(monkeypatch, capsys):
    for report in ('', 'copy: bad\ncopy report: 0 record, 0 array and 0 cell copies; 0 string copies\n'):
        monkeypatch.setattr(copy_report.subprocess, 'run', lambda *args, **kwargs: CompletedProcess(args, 0, report, ''))
        assert copy_report.main(['source.dewy', '--max-copies', '100']) == 1
        assert 'incomplete' in capsys.readouterr().err


def test_density_scope_counts_zero_copy_files_and_excludes_siblings(tmp_path, monkeypatch, capsys):
    import json
    scope = tmp_path / 'source'
    scope.mkdir()
    a = scope / 'a.dewy'
    a.write_text('x=1\n' * 10)
    (scope / 'pure.dewy').write_text('x=1\n' * 10)
    sibling = tmp_path / 'source-old'
    sibling.mkdir()
    b = sibling / 'b.dewy'
    b.write_text('x=1\n')
    report = (f'copy: {a}:1: array copied when binding: source may change\n'
              f'copy: {b}:1: string copied when return: caller owns result\n'
              'copy report: 0 record, 1 array and 0 cell copies; 1 string copies\n')
    monkeypatch.setattr(copy_report.subprocess, 'run', lambda *args, **kwargs: CompletedProcess(args, 0, report, ''))
    args = ['entry.dewy', '--scope', str(scope), '--json']
    assert copy_report.main([*args, '--max-copies-per-kloc', '50']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['count'] == 1 and data['source_lines'] == 20
    assert data['copies_per_kloc'] == 50 and data['within_budget']
    assert copy_report.main([*args, '--max-copies-per-kloc', '49']) == 1
    output = capsys.readouterr()
    assert 'copy density exceeded' in output.err
    assert not json.loads(output.out)['within_budget']
    # An omitted entry outside the scope still invalidates the full report.
    report = report.replace(f'copy: {b}:1: string copied when return: caller owns result\n', '')
    assert copy_report.main(args) == 1
    assert 'incomplete' in capsys.readouterr().err


def test_invalid_density_budget_cannot_pass(monkeypatch):
    import pytest
    monkeypatch.setattr(copy_report.subprocess, 'run', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('must validate first')))
    for value in ['-1', 'nan', 'inf', '1']:
        with pytest.raises(SystemExit):
            copy_report.main(['source.dewy', '--max-copies-per-kloc', value])


def test_scoped_budget_requires_copy_source_provenance(tmp_path, monkeypatch, capsys):
    source = tmp_path / 'entry.dewy'
    source.write_text('x=1\n')
    report = 'copy: ?:0: string copied when stored: source unknown\ncopy report: 0 record, 0 array and 0 cell copies; 1 string copies\n'
    monkeypatch.setattr(copy_report.subprocess, 'run', lambda *args, **kwargs: CompletedProcess(args, 0, report, ''))
    assert copy_report.main([str(source), '--scope', str(source), '--max-copies', '0']) == 1
    assert 'no resolvable source' in capsys.readouterr().err


def test_duplicate_summary_category_is_malformed(monkeypatch, capsys):
    report = 'copy report: 7 record, 0 record, 0 array and 0 cell copies; 0 string copies\n'
    monkeypatch.setattr(copy_report.subprocess, 'run', lambda *args, **kwargs: CompletedProcess(args, 0, report, ''))
    assert copy_report.main(['entry.dewy', '--max-copies', '0']) == 1
    assert 'malformed summary' in capsys.readouterr().err


def test_hosted_summary_includes_moves(monkeypatch, capsys):
    report = ('copy: source.dewy:1: string copied when returned: caller owns result\n'
              'copy report: 0 record, 0 array and 0 cell copies; 1 string escape copy; 2 moves of owned arrays\n')
    monkeypatch.setattr(copy_report.subprocess, 'run', lambda *args, **kwargs: CompletedProcess(args, 0, report, ''))
    for category in ['arrays', 'values']:
        report = report.replace('owned arrays', f'owned {category}')
        assert copy_report.main(['source.dewy', '--max-copies', '1']) == 0
        assert capsys.readouterr().out.startswith('1 copies: 1 string')
