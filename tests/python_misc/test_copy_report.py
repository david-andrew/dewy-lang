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
        return CompletedProcess(command, 0, '', '')
    monkeypatch.setattr(copy_report.subprocess, 'run', run)
    assert copy_report.main(['--compiler', '"/compiler directory/dewy" --debug', 'source.dewy']) == 0
    assert capsys.readouterr().out.startswith('0 copies:')
