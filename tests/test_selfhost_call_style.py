"""The zero-argument call style check, written in Dewy, gives the diagnostics its frozen twin gives."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_call_style_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, ['style/zero_argument_calls'],
                         leaves=('call_style',)) == 1
