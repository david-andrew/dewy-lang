"""The `dewy` command: subcommands are actions, flags are options of a command."""
import subprocess
import sys
from pathlib import Path

import dewy.__main__ as cli

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _dewy(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, '-m', 'dewy', *argv], cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def test_analyze_reports_each_decision_through_the_report_renderer() -> None:
    result = _dewy('analyze', 'dewy/tests/bigint_auto.dewy')
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.count('Info: big integer representation') == 15   # 11 values, and `print`/`printl` instantiated for them 4 times
    assert '╭─[dewy/tests/bigint_auto.dewy:5:16]' in out  # a real source excerpt, not a bare path:line
    assert '`cube` is a big integer: its initializer is one' in out
    assert '15 representation decisions' in out
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


def test_update_downloads_and_runs_the_published_installer(tmp_path: Path, monkeypatch, capsys) -> None:
    installer = tmp_path / 'published-install.sh'
    updated = tmp_path / 'updated'
    installer.write_text(f"#!/bin/sh\nprintf updated > '{updated}'\n")
    installer.chmod(0o755)

    curl = tmp_path / 'curl'
    curl.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = -o ]; then shift; cp \"$PUBLISHED_INSTALLER\" \"$1\"; exit 0; fi\n"
        "  shift\n"
        "done\n"
        "exit 2\n"
    )
    curl.chmod(0o755)
    monkeypatch.setenv('PUBLISHED_INSTALLER', str(installer))
    monkeypatch.setattr(cli.shutil, 'which', lambda command: str(curl) if command == 'curl' else '/bin/bash')

    assert cli.main(['update']) == 0
    assert updated.read_text() == 'updated'
    assert cli.INSTALLER_URL in capsys.readouterr().out


def test_update_reports_a_download_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    curl = tmp_path / 'curl'
    curl.write_text('#!/bin/sh\nexit 22\n')
    curl.chmod(0o755)
    monkeypatch.setattr(cli.shutil, 'which', lambda command: str(curl) if command == 'curl' else '/bin/bash')

    assert cli.main(['update']) == 22
    assert 'failed to download' in capsys.readouterr().err


def test_update_help_does_not_download() -> None:
    result = _dewy('update', '--help')
    assert result.returncode == 0
    assert 'latest published version' in result.stdout
