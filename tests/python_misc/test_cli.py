"""The `dewy` command: subcommands are actions, flags are options of a command."""
import subprocess
import sys
from pathlib import Path

import dewy.__main__ as cli
from udewy.cache import cache_artifact

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


def test_phase_timings_preserve_generated_code_and_program_arguments(tmp_path):
    source = tmp_path / 'timed.dewy'
    source.write_text("main=(args:array<string>):>int64=>if args.length >? 1 and args[1]=?'--timings' 42 else 1\n")
    plain = _dewy('-c', str(source))
    assert plain.returncode == 0, plain.stderr
    assert 'dewy timing ' not in plain.stderr
    code = cache_artifact(source, '.udewy').read_bytes()
    cache_artifact(source).unlink()  # force the same input through every phase
    timed = _dewy('--timings', '-c', str(source))
    assert timed.returncode == 0, timed.stderr
    records = [line.split() for line in timed.stderr.splitlines() if line.startswith('dewy timing ')]
    assert [row[2] for row in records] == ['checking', 'lowering', 'emission', 'backend']
    assert all(len(row) == 5 and row[3].isdigit() and row[4] == 'ns' for row in records)
    assert cache_artifact(source, '.udewy').read_bytes() == code
    run = _dewy(str(source), '--timings')
    assert run.returncode == 42 and 'dewy timing ' not in run.stderr


def test_ordinary_and_debug_builds_keep_separate_metadata_and_caches(tmp_path) -> None:
    source = tmp_path / 'answer.dewy'
    source.write_text('main=():>int64=>{let answer:int64=42 return answer}\n')
    ordinary = _dewy('--compile', str(source))
    assert ordinary.returncode == 0, ordinary.stdout + ordinary.stderr
    code = cache_artifact(source, '.udewy').read_text()
    assert '# @loc ' not in code and '# @var ' not in code
    debug = _dewy('debug', '--build', str(source))
    assert debug.returncode == 0, debug.stdout + debug.stderr
    debug_code = cache_artifact(source, '.debug.udewy').read_text()
    assert '# @loc ' in debug_code and '# @var ' in debug_code
    assert cache_artifact(source, '.udewy').read_text() == code
    for suffix in ['', '.debug']:
        assert subprocess.run([cache_artifact(source, suffix)], check=False).returncode == 42
    assert 'up to date' in _dewy('--compile', str(source)).stdout


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
