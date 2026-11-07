"""The safe-path walk (origins through locals, fields, returns and calls; guards; sinks and their
fixes) agrees with frozen Jo over the programs that use paths and SafePath."""
from pathlib import Path

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

CASES = '''comptime/library_text copies/explicit_array_assignment_2 dogfood/01_wordfreq dogfood/04_todo
dogfood/09_logs dogfood/12_adventure dogfood/14_containers dogfood/16_binary_format dogfood/44_archive_files
dogfood/64_log_analyzer dogfood/84_glob_match dogfood/93_kv_protocol generic/local_replaced generic/value_mut
loop/iterator_tree_walk match/object_patterns match/void_union_trailing_family net/errors object/shadowing
time/machine_zone'''.split()


def test_safe_path_walk_match_twin(compiler, tmp_path, monkeypatch):
    dirs = [p for d in ('contained', 'path') for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    paths = [str(p.relative_to(ROOT)) for p in dirs] + [f'tests/cases/{c}.dewy' for c in CASES]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('safe_path_walk',), paths)
    by = {Path(r[0]).stem: r for r in results}
    assert by['unproven_argument'][2] != 0 and 'not proven to stay inside' in by['unproven_argument'][4]
    assert sum(r[2] == 0 for r in results) > 20
