"""N-D call classification and mutable entry checks agree with frozen Jo."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_nd_contract_query_twins(compiler, tmp_path, monkeypatch):
    # Includes shape failures, handles, mutable entry checks and argument writes.
    contracts = sorted(p.relative_to(ROOT) for p in (ROOT / 'tests/cases/nd_contracts').glob('*.dewy'))
    programs = (*contracts,
                'tests/cases/numeric/matrix_stepped_update.dewy',
                'tests/cases/numeric/matrix_slice_managed.dewy',
                'tests/cases/numeric/matrix_solve.dewy',
                'tests/cases/numeric/matrix_product.dewy',
                'tests/cases/broadcast_facts/gpu_reference.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('nd_contract_query',), programs,
                             flags=((), ('--release',)))
    assert len(results) == 2 * len(programs)
    assert any(code == 0 for _, _, code, *_ in results)
    assert any(code != 0 for _, _, code, *_ in results)
