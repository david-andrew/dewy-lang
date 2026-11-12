"""Named pytest paths select that slice of the suite."""
from tools import core


def test_named_test_path_does_not_add_entire_suite(monkeypatch, tmp_path):
    monkeypatch.setattr(core, 'pytest_python', lambda: tmp_path / 'python')
    monkeypatch.setattr(core, 'test_runner_options', lambda *_: [])
    monkeypatch.setattr(core.subprocess, 'call', lambda command, **_: seen.append(command) or 0)
    monkeypatch.setattr(core, 'twin_scope_env', lambda *_: {})
    monkeypatch.setattr(core, 'twin_scope_summary', lambda *_: None)
    seen = []
    assert core.test(tmp_path / 'compiler', ['tests/test_one.py'], False) == 0
    assert 'tests/test_one.py' in seen[0]
    assert 'tests' not in seen[0]
