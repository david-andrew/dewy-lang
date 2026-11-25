"""Module and prelude bindings preserve overload order, duplicate diagnostics and names arriving through a diamond."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_module_names_twins(compiler, tmp_path, monkeypatch):
    paths = (
        'tests/cases/modules/cycle_diamond.dewy',
        'tests/cases/overload/group_arity.dewy',
        'tests/cases/overload/user_shadows_prelude.dewy',
        'tests/cases/modules/splat_selective_collision.dewy',
    )
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_module_names',), paths)
    assert [r[2] == 0 for r in results] == [True, True, True, False]
