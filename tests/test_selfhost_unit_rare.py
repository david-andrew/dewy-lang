"""Time-library types, constant durations and the unit hints in operator errors agree with frozen Jo."""
from pathlib import Path

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

PROGRAMS = {
    'days.dewy': 'main=()=>{\n    let t=3hour\n    printl(t + 1day)\n}\n',
    'months.dewy': 'main=()=>{\n    let t=3hour\n    printl(t * 2month)\n}\n',
    'hidden.dewy': 'main=()=>{\n    let s="x"\n    let t=3hour\n    printl(t * 4s)\n    printl(t + 0s)\n}\n',
    'duration.dewy': 'main=()=>{\n    let total:Duration=0s\n    let more:Duration=90minute\n    printl("{total} {more}")\n}\n',
}


def test_unit_rare_match_twin(compiler, tmp_path, monkeypatch):
    for name, text in PROGRAMS.items():
        (tmp_path / name).write_text(text)
    cases = sorted(str(p.relative_to(ROOT)) for d in ('time', 'unit', 'units') for p in (ROOT / 'tests/cases' / d).glob('*.dewy'))
    cases += [f'tests/cases/dogfood37_proofs/duration_{c}.dewy' for c in
              ('constant_coerces', 'float_time_rejected', 'of_a_variable_rejected', 'off_grid_rejected', 'other_dimension_rejected')]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('unit_rare',), [*cases, *PROGRAMS])
    by = {Path(r[0]).name: r for r in results}
    assert 'calendar periods' in by['days.dewy'][4] and 'calendar periods' in by['months.dewy'][4]
    assert any(r[2] == 0 for r in results)
