"""Select and wait checks (arms by type and by source, named and conditional waits, race needs,
inbox sources, queue payload clashes, close-arm spins) agree with frozen Jo: the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DIRS = ('select', 'select_named', 'select_sources', 'race_sources', 'race_spread', 'no_deadlocks', 'queues',
        'queue_cancel_wait', 'channels', 'reserve', 'handle', 'type_members', 'match', 'tasks')


def test_select_checks_match_twin(compiler, tmp_path, monkeypatch):
    files = [p for d in DIRS for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    paths = [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('select_checks',), paths)
    assert sum(r[2] == 0 for r in results) > 50 and sum(r[2] != 0 for r in results) > 30
