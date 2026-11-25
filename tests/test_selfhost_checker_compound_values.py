"""Compound updates preserve short circuiting, bit operations, floor division and numeric storage diagnostics."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_compound_values_twins(compiler, tmp_path, monkeypatch):
    paths = (
        'tests/cases/compound/logical_short_circuit.dewy',
        'tests/cases/compound/bitwise_word_assign.dewy',
        'tests/cases/compound/floor_signs.dewy',
        'tests/cases/compound/integer_exact_division.dewy',
    )
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_compound_values',), paths)
    assert [r[2] == 0 for r in results] == [True, True, True, False]


def test_checker_compound_operator_ordinals(compiler, tmp_path, monkeypatch):
    import subprocess
    from tests import selfhost_lsp_double
    from tests.support import ROOT

    driver = """use 'main.jo'
use 'checker_compound_values.dewy'
main = ():
    loop op in [0..87): print(compound_op(op))
"""
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', driver)
    expected = [0] * 48 + list(range(58, 66)) + [67, 68] + [0] * 29
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('checker_compound_values',)):
        result = subprocess.run([binary], check=True, capture_output=True, timeout=60)
        assert list(map(int, result.stdout.splitlines())) == expected
