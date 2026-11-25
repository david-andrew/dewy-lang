from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_optional_twins_preserve_wide_fallback(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, ['exact_int/coalesce_wide_shift'],
                         leaves=('checker_optional',)) == 1
