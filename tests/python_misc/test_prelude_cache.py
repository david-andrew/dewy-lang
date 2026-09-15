"""The checked-prelude cache: identical output with and without it, and resilience to a bad entry."""
import os

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


OTHER = 'let Err = type of error & [message:string]\nlet main = ():>int64 => { let d:dict<string int64> = ["a" -> 1]  if "a" in? d return 42  return 1 }\n'


def test_resident_prelude_gives_identical_output_across_compiles() -> None:
    """A process keeps the restored prelude and rolls a compile's additions back:
    the same program spells the same µDewy on every compile, before and after
    another program (its brands, error types, generic instances, dictionary
    names), and the same as a fresh process — with or without the cache."""
    import subprocess
    import sys

    from dewy.semantic import modules
    first = codegen(SrcFile(None, SOURCE))
    assert len(modules._resident_preludes) == 1
    resident = next(iter(modules._resident_preludes.values()))
    registry = resident.state['registry']
    assert registry.next_id > resident.next_id   # the compile's own bindings are there…
    codegen(SrcFile(None, OTHER))
    assert codegen(SrcFile(None, SOURCE)) == first
    assert registry.next_id > resident.next_id
    # Restoring the nominal graph must discard reachability learned from a
    # previous compilation's added edges as well as its added names.
    system = resident.state['type_system']
    system.add_type('TemporaryNominal', 'exception')
    assert system.is_subtype('TemporaryNominal', 'exception')
    resident.rollback()
    assert not system.is_subtype('TemporaryNominal', 'exception')
    assert registry.next_id == resident.next_id and set(resident.state['records']) == set(resident.records)   # …until the next compile starts
    program = f"from dewy.backend.udewy import codegen\nfrom dewy.reporting import SrcFile\nimport sys\nsys.stdout.write(codegen(SrcFile(None, {SOURCE!r})))"
    for variable in ('DEWY_NO_RESIDENT_PRELUDE', 'DEWY_NO_PRELUDE_CACHE'):
        fresh = subprocess.run([sys.executable, '-c', program], capture_output=True, text=True, env={**os.environ, variable: '1'}, check=True)
        assert fresh.stdout == first, variable


def test_cached_binding_registry_rebuilds_syntax_identity() -> None:
    import pickle

    from dewy.reporting import Span
    from dewy.semantic.bindings import BindingRegistry

    registry = BindingRegistry()
    syntax = object()
    binding = registry.allocate(syntax, 'saved', 'function', Span(0, 1))
    # Model an address from the process that wrote the cache. It must never
    # identify an unrelated node in the process that restores it.
    unrelated = object()
    registry.by_syntax = {id(unrelated): binding}
    restored = pickle.loads(pickle.dumps(registry))
    saved = restored.by_id[binding.id]
    assert restored.by_syntax == {id(saved.syntax): saved}
    assert id(unrelated) not in restored.by_syntax
    fresh = restored.allocate(unrelated, 'fresh', 'value', Span(1, 2))
    assert fresh.id != saved.id
    assert restored.by_syntax[id(saved.syntax)] is saved


@pytest.mark.parametrize('resident', [False, True])
def test_transitive_prelude_input_invalidates_checked_state(tmp_path, monkeypatch, resident):
    from dewy.semantic import modules, prelude as prelude_config

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('DEWY_NO_PRELUDE_CACHE', raising=False)
    if resident:
        monkeypatch.delenv('DEWY_NO_RESIDENT_PRELUDE', raising=False)
    else:
        monkeypatch.setenv('DEWY_NO_RESIDENT_PRELUDE', '1')
    dependency = tmp_path / 'dependency.dewy'
    dependency.write_text('const answer:int64=42\n')
    prelude = tmp_path / 'prelude.dewy'
    prelude.write_text('import dependency as dependency\nconst answer:int64=dependency.answer\n')
    monkeypatch.setattr(prelude_config, 'library', tmp_path)
    monkeypatch.setattr(modules, 'prelude_files', lambda target: (prelude,))
    validated = []
    original = ModuleCompiler._validate_and_select

    def observe(self, root, srcfile, **kwargs):
        validated.append(srcfile.path)
        return original(self, root, srcfile, **kwargs)

    monkeypatch.setattr(ModuleCompiler, '_validate_and_select', observe)
    source = SrcFile(None, 'main=():>int64=>answer\n')
    cold = codegen(source)
    validated.clear()
    assert codegen(source) == cold
    assert dependency not in validated and prelude not in validated
    # The resident state now also contains the entry compilation's additions.
    # Input checking must use the prelude's original records before rollback.
    assert codegen(source) == cold
    stamp = dependency.stat()
    dependency.write_text('const answer:int64=43\n')
    os.utime(dependency, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    validated.clear()
    changed = codegen(source)
    assert changed != cold
    assert dependency in validated and prelude in validated
    validated.clear()
    assert codegen(source) == changed
    assert dependency not in validated and prelude not in validated
    monkeypatch.setenv('DEWY_NO_PRELUDE_CACHE', '1')
    assert codegen(source) == changed
    assert dependency in validated and prelude in validated
