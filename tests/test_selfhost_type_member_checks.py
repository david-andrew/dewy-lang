"""Type-valued members and handles (`T & U` meets, handle `.types`, outcome shorthands and their
clashes, generic families) agree with frozen Jo: the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DIRS = ('type_members', 'queues', 'queue_nested_optional', 'protocols', 'select', 'select_named', 'select_sources',
        'race_sources', 'generic_names', 'gpu_broadcast', 'gpu_word_memory', 'rest_params', 'channels')


def test_type_member_checks_match_twin(compiler, tmp_path, monkeypatch):
    files = [p for d in DIRS for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    paths = [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('type_member_checks',), paths)
    assert sum(r[2] == 0 for r in results) > 40 and sum(r[2] != 0 for r in results) > 20
