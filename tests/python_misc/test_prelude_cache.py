"""The checked-prelude cache: identical output with and without it, and resilience to a bad entry."""
import os
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.modules import ModuleCompiler

SOURCE = 'let main = ():>int64 => { let file = p"a/b.c"  printl"{file.parent}"  return 42 }\n'


def test_cached_prelude_gives_identical_output(monkeypatch: pytest.MonkeyPatch) -> None:
    cache_path = ModuleCompiler(SrcFile(None, SOURCE), 'x86_64')._checked_prelude_path()
    assert cache_path is not None and cache_path.parent.name == 'prelude'
    cached = codegen(SrcFile(None, SOURCE))
    assert cache_path.is_file()
    monkeypatch.setenv('DEWY_NO_PRELUDE_CACHE', '1')
    assert codegen(SrcFile(None, SOURCE)) == cached


def test_corrupt_cache_entry_is_ignored_and_rewritten() -> None:
    compiler = ModuleCompiler(SrcFile(None, SOURCE), 'x86_64')
    cache_path = compiler._checked_prelude_path()
    assert cache_path is not None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(b'not a pickle')
    assert codegen(SrcFile(None, SOURCE))   # checks the prelude itself
    assert cache_path.stat().st_size > 1000  # and rewrote the entry


def test_restore_marks_the_prelude_loaded() -> None:
    compiler = ModuleCompiler(SrcFile(None, SOURCE), 'x86_64')
    compiler._ensure_prelude()
    assert compiler.prelude_loaded and 'p' in compiler.prelude_bindings and 'run' in compiler.prelude_bindings
