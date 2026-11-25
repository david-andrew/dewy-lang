"""Source dispatch and quote scanning agree with frozen ownership."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_build_double import compare_builds
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_source_frontend_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_EMIT_WORKERS', '1')
    paths = ['tests/ladder/99_dewy_frontend/design.dewy']
    for pattern in ('loopx/*.dewy', 'loop_else/*.dewy', 'lazy/*.dewy', 'string/*.dewy', 'generic/*.dewy'):
        paths += [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'tests/cases').glob(pattern))[:4]]
    result = compare_builds(compiler, tmp_path, monkeypatch, ('source_frontend',), paths,
                            flags=((), ('--release',), ('--ir',)))
    assert sum(row[2] == 0 for row in result) >= 9


def test_source_frontend_quotes(compiler, tmp_path, monkeypatch):
    driver = r'''use 'main.jo'
use 'source_frontend.dewy'
main = ():
    loop text in ["\"abc\"", "r\"a\\b\"", "\"{1 + 2}\"", "\"unfinished", "\"\"\"a\nb\"\"\""]:
        start = if text[0] == 'r': 1 else: 0
        print("{source_quote_end(text, start, start == 1)}")
'''
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', driver)
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    results = [subprocess.run([binary], capture_output=True, timeout=30)
               for binary in leaf_compilers(compiler, tmp_path, ('source_frontend',))]
    assert all(r.returncode == 0 for r in results), [r.stderr for r in results]
    assert results[0].stdout == results[1].stdout and len(results[0].stdout.splitlines()) == 5
