"""Demanded once-only regex globals agree with the frozen lowering entry."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_build_double import compare_builds
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


def test_lower_entries_twins(compiler, tmp_path, monkeypatch):
    paths = [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'tests/cases/search').glob('regex*.dewy'))[:8]]
    assert paths
    result = compare_builds(compiler, tmp_path, monkeypatch, ('lower_entries',), paths,
                            flags=((), ('--release',), ('--ir',)))
    assert any(row[2] == 0 for row in result)


def test_lower_entries_reset(compiler, tmp_path, monkeypatch):
    driver = r'''use 'main.jo'
use 'lower.jo'
use 'lower_entries.dewy'
use 'check_constant.jo'
main = ():
    once_slots[42] = 7
    once_prepare(false)
    assert(once_slots.len() == 0)
    once_slots[43] = 8
    cc_passed = {}
    once_prepare(true)
    assert(once_slots.len() == 0)
    print("reset")
'''
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', driver)
    results = [subprocess.run([binary], capture_output=True, timeout=30)
               for binary in leaf_compilers(compiler, tmp_path, ('lower_entries',))]
    assert all(r.returncode == 0 for r in results), [r.stderr for r in results]
    assert results[0].stdout == results[1].stdout == b'reset\n'
