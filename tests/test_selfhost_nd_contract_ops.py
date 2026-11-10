"""N-d contracts (shape signatures and terms, field shapes, the rank, dims, count and validity of
an n-d value, its make, capture, broadcast, transpose, upload, download and store facts) agree
with frozen Jo: the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DIRS = ('nd_contracts', 'gpu_nonempty', 'gpu_integer_upload', 'record_field_shape', 'library_contracts', 'notraps16_shapes',
        'gpu_upload_shape', 'gpu_broadcast', 'refine_selection_output', 'tensor_shape_flow', 'tensor', 'broadcast_facts')


def test_nd_contract_ops_match_twin(compiler, tmp_path, monkeypatch):
    files = [p for d in DIRS for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    files += sorted((ROOT / 'tests/cases/notraps24').glob('shape_loop_*.dewy'))
    files += sorted((ROOT / 'tests/cases/facts').glob('*nd*.dewy')) + sorted((ROOT / 'tests/cases/facts').glob('*shape*.dewy'))
    paths = [str(p.relative_to(ROOT)) for p in dict.fromkeys(files)]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('nd_contract_ops',), paths)
    assert sum(r[2] == 0 for r in results) > 40 and sum(r[2] != 0 for r in results) > 20
