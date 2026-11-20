from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_call_style_twins_after_multibyte_interpolation(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, ['style/interpolated_call_after_emoji'],
                         leaves=('call_style',)) == 1
