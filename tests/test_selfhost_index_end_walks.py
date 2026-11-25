"""Scalar indexes, slices and empty receivers use the same end substitution in both compilers."""

import subprocess

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
from tests.test_end_index_cost import FORMS, RUNTIME_CHECKS, SOURCE
import pytest

pytestmark = pytest.mark.nightly


def test_index_end_walks_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    source = tmp_path / 'end_index.dewy'
    source.write_text(RUNTIME_CHECKS + SOURCE.format(**FORMS[0]))
    paths = [source, 'tests/cases/sequence/extend_slices.dewy', 'tests/cases/range/index_error_9.dewy',
             'tests/cases/range/index_error_10.dewy']
    results = compare_builds(compiler, tmp_path, monkeypatch, ('index_end_walks',), paths,
                             flags=((), ('--release',)))
    assert all(r[2] == 0 for r in results)
    for i, diagnostic in [(2, b'out of bounds (length 0)'), (3, b'string index out of bounds')]:
        run = subprocess.run([tmp_path / 'dewy' / f'p{i}-0'], capture_output=True, timeout=30)
        assert run.returncode == 101 and diagnostic in run.stderr
