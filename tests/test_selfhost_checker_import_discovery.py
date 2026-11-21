"""Sibling and missing module searches and compiler-supplied imports match the frozen checker."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_import_discovery_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    (tmp_path / 'helper.dewy').write_text('answer=():>int64=>42\n')
    sibling = tmp_path / 'sibling.dewy'
    sibling.write_text('import helper\nmain=()=>printl(helper.answer())\n')
    missing = tmp_path / 'missing.dewy'
    missing.write_text('import no_such_sibling\nmain=()=>printl(0)\n')
    paths = (sibling, 'tests/cases/rational/builtin.dewy', missing)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_import_discovery',), paths)
    assert all(r[2] == 0 for r in results[:2])
    assert results[-1][2] != 0 and "cannot find module 'no_such_sibling'" in results[-1][4]
