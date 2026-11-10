"""Place updates (tuple slot writes, annotated local places, shaped declarations and returns, selection,
pool and index updates through end, unused values, mismatched assignments) agree with frozen Jo:
the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DIRS = ('tuple_slot_write', 'pool_fixed_update', 'end', 'refine_selection_output', 'slice_assign_extents', 'nd_contracts',
        'notraps16_shapes', 'notraps24', 'copies', 'argument', 'dict_refine', 'juxtaposition', 'multi', 'semicolon_narrow',
        'numbers', 'compound', 'grouped_place', 'refine_lent_annotation', 'positional')


def test_checks_place_updates_match_twin(compiler, tmp_path, monkeypatch):
    files = [p for d in DIRS for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    paths = [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checks_place_updates',), paths)
    assert sum(r[2] == 0 for r in results) > 50 and sum(r[2] != 0 for r in results) > 30
