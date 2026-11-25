"""Owner cleanup survives callable erasure and transfer into a match binding."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_batchhang2_lower_group_twins(compiler, tmp_path, monkeypatch):
    paths = sorted(str(path) for path in (ROOT / 'tests/cases/batchhang2').glob('*.dewy'))
    result = compare_builds(compiler, tmp_path, monkeypatch, ('lower_group',), paths,
                            flags=((), ('--release',)))
    assert all(row[2] == 0 for row in result)
