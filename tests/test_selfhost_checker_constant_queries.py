"""Resolved constants and integer type arguments use the same binding and fixed-width range rules."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_constant_queries_twins(compiler, tmp_path, monkeypatch):
    paths = (
        'tests/cases/decided_integer_arguments/named.dewy',
        'tests/cases/decided_integer_arguments/qualified.dewy',
        'tests/cases/decided_integer_arguments/wide_name.dewy',
        'tests/cases/decided_integer_arguments/runtime_name.dewy',
    )
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_constant_queries',), paths)
    assert [r[2] == 0 for r in results] == [True, True, False, False]


def test_checker_static_integer_bounds(compiler, tmp_path, monkeypatch):
    import subprocess
    from tests import selfhost_lsp_double
    from tests.support import ROOT

    driver = """use 'main.jo'
use 'checker_constant_queries.dewy'
use 'type_ops.dewy'
use 'types.jo'
main = ():
    init_types()
    loop t in [0, T_BOOL, T_STR, T_I8, T_U8, T_INT, T_U64]:
        loop v in [-9223372036854775807 - 1, -129, -128, -1, 0, 127, 128, 255, 256, 9223372036854775807]: print(sa_fits(v, t))
"""
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', driver)
    values = (-(1 << 63), -129, -128, -1, 0, 127, 128, 255, 256, (1 << 63) - 1)
    domains = ((), values, (), range(-128, 128), range(256), values, range(1 << 64))
    expected = [str(value in domain).lower() for domain in domains for value in values]
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('checker_constant_queries',)):
        result = subprocess.run([binary], check=True, capture_output=True, text=True, timeout=60)
        assert result.stdout.splitlines() == expected
