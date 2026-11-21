"""The module name index chooses the same homes and reports the same ambiguous imports as its twin."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_checker_home_index_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    paths = ('tests/ladder/98_notes_listen/design.dewy',
             'tests/cases/batch4_entry/splat.dewy',
             'tests/cases/modules/splat_selective_collision.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_home_index',), paths)
    assert results[0][2] == results[1][2] == 0
    assert results[2][2] != 0


def test_bound_in_walks_all_module_homes(compiler, tmp_path, monkeypatch):
    driver = """use 'main.jo'
use 'check.jo'
use 'checker_home_index.dewy'
main = ():
    home_add(1, 2)
    home_add(3, 2)
    home_add(3, 2)
    print("{bound_in(1, 2)}:{bound_in(3, 2)}:{bound_in(2, 2)}:{bound_in(1, 0)}:{bound_in(1, 1000)}:{home_mod.len()}")
"""
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', driver)
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('checker_home_index',)):
        result = subprocess.run([binary], check=True, capture_output=True, timeout=30)
        assert result.stdout == b'true:true:false:false:false:2\n'


def test_use_home_classifies_visible_module_sources(compiler, tmp_path, monkeypatch):
    driver = """use 'main.jo'
use 'check.jo'
use 'checker_home_index.dewy'
main = ():
    modules = [Module(), Module(), Module()]
    modules[0].uses = [1]
    modules[1].names[5] = 17
    modules[2].names[6] = 18
    print("{use_home(1, 5)}:{use_home(0, 5)}:{use_home(0, 6)}:{use_home(0, 7)}")
    home_add(2, 5)
    print(use_home(0, 5))
    prelude_used = [true]
    print(use_home(0, 6))
"""
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', driver)
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('checker_home_index',)):
        result = subprocess.run([binary], check=True, capture_output=True, timeout=30)
        assert result.stdout == b'-1:1:-1:-1\n-2\n-2\n'
