"""Ladder programs that must be rejected pass only on a matching semantic diagnostic."""
import subprocess
from pathlib import Path
import pytest
from tools import ladder

SOURCE = Path('/ladder/65_example/design.dewy')
EXPECT = {'kind': 'compile-error', 'diagnostic': 'implicit costly copy|explicit cop', 'line': 37}


def check(code, stderr):
    return subprocess.CompletedProcess(['dewy-core', 'check'], code, '', stderr)


@pytest.mark.parametrize('code,stderr,status', [
    (0, '', 'wrongly-accepted'),
    (1, f'{SOURCE}:37:15: error: implicit costly copy of array<int64>: use `.copy`\n', 'rejected'),
    (1, f'{SOURCE}:12:15: error: implicit costly copy of array<int64>: use `.copy`\n', 'other-error'),
    (1, f'{SOURCE}:37:15: error: unknown name \'xs\'\n', 'other-error'),
    (1, f'{SOURCE}:37:5: error: `$lend` is part of the design but not implemented yet\n', 'unsupported'),
    (1, f'{SOURCE}:37:5: error: Dewy core experiment does not yet support this type expression\n', 'unsupported'),
    (1, f'{SOURCE}:37:1: error: unknown directive `$copy` (a loop label goes on its own line)\n', 'unsupported'),
    (1, f'{SOURCE}:37:11: error: expected an expression, found \']\'\n', 'parse-error'),
    (1, f'{SOURCE}:37:11: error: unterminated string\n', 'parse-error'),
])
def test_rejection_status(code, stderr, status):
    result = ladder.rejection('65_example', SOURCE, check(code, stderr), EXPECT)
    assert result.status == status
    assert result.ok == (status == 'rejected')


def test_rejection_without_a_line_matches_anywhere():
    stderr = f'{SOURCE}:9:1: error: Explicit copy needed here\n'
    result = ladder.rejection('65_example', SOURCE, check(1, stderr), {'kind': 'compile-error', 'diagnostic': 'explicit cop'})
    assert result.ok


def test_open_programs_cannot_join_the_ratchet(monkeypatch, tmp_path):
    for name in ('01_a', '02_b'):
        (tmp_path / name).mkdir()
        (tmp_path / name / 'design.dewy').write_text('')
    (tmp_path / '01_a' / 'expected.out').write_text('')
    monkeypatch.setattr(ladder, 'LADDER', tmp_path)
    doc = {'milestones': {'1': 'One'}, 'design_passing': ['01_a', '02_b'],
           'programs': {'01_a': {'milestone': 1, 'open': 'question'},
                        '02_b': {'milestone': 1, 'expect': {'kind': 'compile-error', 'diagnostic': '('}}}}
    problems = ladder.validate(doc)
    assert '01_a is open and cannot be in design_passing' in problems
    assert '02_b needs expect.diagnostic, a regular expression' in problems
