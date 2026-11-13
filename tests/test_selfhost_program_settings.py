"""Program configuration and its reused call inventory agree with frozen twins."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_program_settings_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch,
                         ['batch4_settings/reach', 'batch4_settings/conflict'],
                         leaves=('program_settings', 'directive_ops', 'panic_inventory')) == 2
