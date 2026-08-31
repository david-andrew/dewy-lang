"""Compiles that fail are written up (sources included) when recording is on."""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _dewy(*argv: str, cwd: Path, log: str | None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    if log is None:
        env.pop('DEWY_FAILURE_LOG', None)
    else:
        env['DEWY_FAILURE_LOG'] = log
    return subprocess.run([sys.executable, '-m', 'dewy', *argv], cwd=cwd, env=env, capture_output=True, text=True, check=False)


def test_failed_compile_is_recorded_with_every_source_it_read(tmp_path: Path) -> None:
    (tmp_path / 'helper.dewy').write_text('helper_value = 42\n')
    (tmp_path / 'bad.dewy').write_text("import [path='helper.dewy']\nmain = () => {\n    x:int = 'nope'\n    printl(helper_value)\n}\n")
    log = tmp_path / 'failures'
    result = _dewy('bad.dewy', cwd=tmp_path, log=str(log))
    assert result.returncode != 0
    assert '(failure recorded at' in result.stderr
    records = list(log.glob('*-bad.md'))
    assert len(records) == 1
    text = records[0].read_text()
    assert text.startswith('# compile failure: bad.dewy')
    assert '- command: `dewy bad.dewy`' in text
    assert "expected `int`, got `'nope'`" in text and '\x1b[' not in text
    assert f'### {(tmp_path / "bad.dewy").resolve()}' in text and "x:int = 'nope'" in text
    assert f'### {(tmp_path / "helper.dewy").resolve()}' in text and 'helper_value = 42' in text
    assert 'library/linux/system.dewy' not in text.split('### library')[0]   # library files are listed, never inlined


def test_dewy_test_records_a_module_that_did_not_build(tmp_path: Path) -> None:
    (tmp_path / 't.dewy').write_text('$test\nbroken = () => { y:int = "s" }\n')
    log = tmp_path / 'failures'
    assert _dewy('test', 't.dewy', cwd=tmp_path, log=str(log)).returncode == 102
    assert len(list(log.glob('*-t.md'))) == 1


def test_recording_is_off_under_pytest_and_when_disabled(tmp_path: Path) -> None:
    (tmp_path / 'bad.dewy').write_text("main = () => { x:int = 'nope' }\n")
    (tmp_path / 'ok.dewy').write_text('main = () => printl(1)\n')
    log = tmp_path / 'failures'
    assert 'recorded' not in _dewy('bad.dewy', cwd=tmp_path, log=None).stderr     # PYTEST_VERSION is inherited
    assert 'recorded' not in _dewy('bad.dewy', cwd=tmp_path, log='0').stderr
    assert _dewy('ok.dewy', cwd=tmp_path, log=str(log)).returncode == 0
    assert not log.exists()   # a successful compile writes nothing
