"""Traversal remains exhaustive without making every reader an I/O operation."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_capture_readers_keep_one_symbol_index(tmp_path):
    source = ROOT / 'tests/fixtures/native_capture_readers.dewy'
    output = tmp_path / 'readers.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                            text=True, timeout=10, check=False)
    assert result.returncode == 42, result.stderr
    # Payload allocation, not peak RSS: repeatedly freed/rebuilt indexes must
    # fail this budget too. The same fixture is run through the native CLI.
    assert 0 <= int(result.stdout) < 20_000_000


def test_unhandled_hir_variant_still_reports_an_internal_error(tmp_path):
    source = tmp_path / 'traversal.dewy'
    source.write_text(f'''from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
Unvisited=type of hir.AST & []
main=(argv:array<string>):>int64=>{{
    let loc=Span[0 0]
    if argv.length >? 1 {{
        hir.children(Unvisited[loc 0]);
        return 1
    }}
    let children=hir.children(hir.RangeMembership[loc 0 17 23])
    if children.length not=? 2 return 2
    if children[0] not=? 17 or children[1] not=? 23 return 3
    if hir.children(hir.Void[loc 0]).length not=? 0 return 4
    return 42
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    binary = cache_artifact(output).resolve()
    result = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 42, result.stderr
    result = subprocess.run([binary, 'unhandled'], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 101
    assert 'internal compiler error: no HIR traversal for' in result.stderr
