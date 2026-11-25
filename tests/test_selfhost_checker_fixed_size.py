"""Literal and named Jo array lengths, Dewy lengths, and size diagnostics agree with the twin."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_fixed_size_twins(compiler, tmp_path, monkeypatch):
    paths = []
    for name, n in [('named', 'limit'), ('zero', '0'), ('large', '268435457')]:
        path = tmp_path / f'{name}.jo'
        path.write_text(f'const limit = 4\nmain = ():\n    xs: int[{n}]\n    print(xs.len())\n')
        paths.append(path)
    paths.append('tests/cases/fixed/array_zero_length.dewy')
    rows = compare_builds(compiler, tmp_path, monkeypatch, ('checker_fixed_size',), paths)
    assert rows[0][2] == 0
    assert rows[1][2] != 0 and 'at least 1' in rows[1][4]
    assert rows[2][2] != 0 and 'too large' in rows[2][4]
    assert rows[3][2] != 0
