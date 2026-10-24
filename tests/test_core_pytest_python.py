"""`tools.core test` runs pytest under a Python that has it, or stops before the cases saying how to get one."""
import sys
from pathlib import Path

import pytest

from tools import core


@pytest.mark.core_quick
def test_pytest_python_prefers_a_venv_with_pytest(tmp_path, monkeypatch):
    venv = tmp_path / '.venv/bin/python3'
    venv.parent.mkdir(parents=True)
    venv.write_text('')
    monkeypatch.setattr(core, 'has_pytest', lambda python: python == venv)
    assert core.pytest_python(tmp_path) == venv


@pytest.mark.core_quick
def test_pytest_python_falls_back_to_the_current_python(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'has_pytest', lambda python: python == Path(sys.executable))
    assert core.pytest_python(tmp_path) == Path(sys.executable)


@pytest.mark.core_quick
def test_missing_pytest_stops_before_the_cases(tmp_path, monkeypatch, capsys):
    from tools import cases

    monkeypatch.setattr(core, 'has_pytest', lambda python: False)
    monkeypatch.setattr(cases, 'discover', lambda **_: pytest.fail('cases ran without pytest'))
    assert core.test(tmp_path / 'dewy', [], quick=True) == 2
    assert 'pytest is missing' in capsys.readouterr().err
