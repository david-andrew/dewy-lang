"""The uniform insertion spelling retains set mutation and value semantics."""
import subprocess
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from udewy.cache import cache_artifact
from udewy.frontend import entry_point, EntryPointOptions
from test_bootstrap_lowering import ROOT


def test_set_push(tmp_path):
    source = ROOT / 'tests/fixtures/uniform_set_push.dewy'
    output = tmp_path / 'set-push.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    assert subprocess.run([cache_artifact(output).resolve()], timeout=5).returncode == 42


def test_const_set_push_is_rejected():
    with pytest.raises(UserError, match='const'):
        codegen(SrcFile(None, 'let main=():>int64=>{const s:set<int64>=set[] s.push(1) return 0}'))
