"""Explicit aggregate snapshots preserve values and source-level intent."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point
from test_bootstrap_lowering import ROOT


@pytest.mark.parametrize("fixture", ["explicit_aggregate_copy", "explicit_copy_lifetimes"])
def test_explicit_aggregate_copy(tmp_path, fixture):
    source = ROOT / f'tests/fixtures/{fixture}.dewy'
    output = tmp_path / 'copy.udewy'
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr


def test_copy_rejects_arguments():
    with pytest.raises(UserError):
        codegen(SrcFile(None, 'main=():>int64=>{let xs:array<int64>=[1] let ys=xs.copy(2) return 0}'))


def test_copy_keeps_explicit_intent_in_report():
    from dewy.backend.udewy import lower
    codegen(SrcFile(None, 'main=():>int64=>{let xs:array<int64>=[1] let ys=xs.copy() return xs.length+ys.length}'))
    assert any(note.explicit and note.kind == 'array' for note in lower.last_copy_notes)


def test_copy_does_not_share_length_facts():
    with pytest.raises(UserError, match='not proven in bounds'):
        codegen(SrcFile(None, '''
R:type=[xs:array<int64>]
main=():>int64=>{
 let original=R[[1]]
 let snapshot=original.copy()
 snapshot.xs.push(2)
 return original.xs[1]
}
'''))


def test_declared_copy_member_takes_precedence(tmp_path):
    output = tmp_path / 'member.udewy'
    output.write_text(codegen(SrcFile(None, 'R:type=[copy:int64] main=():>int64=>{let value=R[42] return value.copy}')))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    assert subprocess.run([cache_artifact(output).resolve()], timeout=5).returncode == 42
