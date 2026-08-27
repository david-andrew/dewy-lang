"""The `dewy` command: subcommands are actions, flags are options of a command."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _dewy(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, '-m', 'dewy', *argv], cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def test_analyze_reports_each_decision_through_the_report_renderer() -> None:
    result = _dewy('analyze', 'dewy/tests/bigint_auto.dewy')
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.count('Info: big integer representation') == 11
    assert '╭─[dewy/tests/bigint_auto.dewy:5:16]' in out  # a real source excerpt, not a bare path:line
    assert '`cube` is a big integer: its initializer is one' in out
    assert '11 representation decisions' in out
    assert '\x1b[' not in out  # no ANSI colors when stdout is not a terminal


def test_analyze_says_when_every_integer_is_a_word() -> None:
    result = _dewy('analyze', 'dewy/tests/abstract_int.dewy')
    assert result.returncode == 0, result.stderr
    assert 'every integer is a 64-bit word' in result.stdout
    assert 'big integer representation' not in result.stdout


def test_analyze_is_a_subcommand_not_a_flag() -> None:
    assert _dewy('--analyze', 'dewy/tests/bigint_auto.dewy').returncode != 0
    assert 'analysis decisions' in _dewy('analyze', '--help').stdout


def test_version_flag_belongs_to_the_top_level_command() -> None:
    result = _dewy('--version')
    assert result.returncode == 0 and result.stdout.startswith('dewy ')
