"""Dotted elementwise operations (flat and n-d broadcast loops, GPU fragment programs, new axes and
their hints) agree with frozen Jo: the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DIRS = ('broadcast_facts', 'broadcast_places', 'new_axis', 'gpu_broadcast', 'gpu_integer_ops', 'gpu_integer_upload',
        'gpu_upload_shape', 'gpu_ieee', 'gpu', 'gpu_float_sum', 'tensor', 'tensor_shape_flow', 'refine_selection_output',
        'compound', 'fan_out', 'inference')


def test_dotted_checks_match_twin(compiler, tmp_path, monkeypatch):
    files = [p for d in DIRS for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    files += sorted((ROOT / 'tests/cases/numeric').glob('*dot*.dewy')) + sorted((ROOT / 'tests/cases/numeric').glob('*bcast*.dewy'))
    paths = [str(p.relative_to(ROOT)) for p in dict.fromkeys(files)]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('dotted_checks',), paths)
    assert sum(r[2] == 0 for r in results) > 40 and sum(r[2] != 0 for r in results) > 20
