"""Map key and entry facts agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'facts/field_key_guard',
    'fixed/array_dictionary',
    'set/copy_and_removal',
    'notraps17_get/count',
]


def test_facts_maps_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
