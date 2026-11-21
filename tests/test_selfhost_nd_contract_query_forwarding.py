"""Direct shape forwarding agrees with the frozen N-D contract query."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_nd_contract_query_forwarding_twins(compiler, tmp_path, monkeypatch):
    programs = ('tests/cases/census_proofs/nd_forward_shape.dewy',
                'tests/cases/census_proofs/nd_replaced_shape.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('nd_contract_query',),
                             programs, flags=((), ('--release',)))
    assert len(results) == 4
    assert sum(result[2] == 0 for result in results) == 2
