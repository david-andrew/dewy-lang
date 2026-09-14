"""Imported runtime dependencies survive pruning before hosted lowering."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import TypeCheckError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_imported_callbacks_defaults_and_initialization(tmp_path, monkeypatch):
    library = tmp_path / 'dependency.dewy'
    library.write_text('''
initialize=():>int64=>6
stamp=initialize()
helper=():>int64=>36
read=(n:int64=helper()):>int64=>n+stamp
callback=():>int64=>read()
table:array<():>int64>=[@callback]
unused=():>int64=>999
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''
import p"dependency.dewy" as dependency
main=():>int64=>{
    if dependency.table.length =? 0 return 1
    return dependency.table[0]()
}
''')
    monkeypatch.chdir(tmp_path)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    emitted = output.read_text()
    assert '_dependency_unused' not in emitted
    for name in ('initialize', 'helper', 'read', 'callback'):
        assert f'_dependency_{name}' in emitted
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=10)
        assert result.returncode == 42, result.stderr


def test_entry_hir_stays_complete_without_main(tmp_path):
    source = tmp_path / 'library.dewy'
    source.write_text('let first=():>int64=>41\nlet second=():>int64=>first()+1\n')
    root = check.typecheck_and_resolve(SrcFile.from_path(source), include_prelude=False)
    assert isinstance(root, hir.Block)
    assert {node.name for node in root.items if isinstance(node, hir.Declare)} >= {'first', 'second'}


def test_unused_imported_body_still_gets_checked(tmp_path):
    (tmp_path / 'dependency.dewy').write_text('unused=():>int64=>"wrong type"\n')
    source = tmp_path / 'main.dewy'
    source.write_text('import p"dependency.dewy" as dependency\nmain=():>int64=>42\n')
    with pytest.raises(TypeCheckError):
        codegen(SrcFile.from_path(source))
