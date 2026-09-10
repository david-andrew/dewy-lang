"""Known duplicate values must still evaluate their member expressions."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize(('literal', 'element'), [('1', 'int64'), ('"same"', 'string')])
def test_singleton_returning_set_members_keep_all_calls(tmp_path, literal, element):
    source = SrcFile(None, f'''let calls:int64=0
let next=():>{literal}=>{{calls+=1 return {literal}}}
let main=():>int64=>{{
    let values:set<{element}>=set[next() next()]
    return if calls=?2 and values.length=?1 42 else 0
}}
''')
    output = tmp_path / 'set_effects.udewy'
    output.write_text(codegen(source))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=30, check=False)
    assert result.returncode == 42, result.stderr


def test_singleton_returning_array_members_keep_all_calls(tmp_path):
    source = SrcFile(None, '''let calls:int64=0
let next=():>1=>{calls+=1 return 1}
let main=():>int64=>{
    let values:array<int64>=[next() next()]
    return if calls=?2 and values.length=?2 42 else 0
}
''')
    output = tmp_path / 'array_effects.udewy'
    output.write_text(codegen(source))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=30, check=False)
    assert result.returncode == 42, result.stderr
