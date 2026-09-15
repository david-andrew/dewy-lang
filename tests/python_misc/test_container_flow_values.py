"""Dictionary/set alternatives use the same owned flow result as records."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('target', ['x86_64', 'c'])
@pytest.mark.parametrize('body', [
    '''let original:dict<string int64>=['answer'->42]
    let other:dict<string int64>=['answer'->99]
    let choose=(flag:bool):>dict<string int64>=>if flag original else other
    let a=choose(true)
    let b=choose(false)
    a['answer']=7
    b['answer']=8
    let literal=if flag ['answer'->42] else ['answer'->99]
    return if original['answer']=?42 and other['answer']=?99 literal.get('answer' 0) else 1''',
    '''let original:set<int64>=set[42]
    let other:set<int64>=set[99]
    let choose=(flag:bool):>set<int64>=>if flag original else other
    let a=choose(true)
    let b=choose(false)
    a.add(7)
    b.add(8)
    let literal=if flag set[42] else set[99]
    return if original.length=?1 and other.length=?1 and 42 in? literal 42 else 1''',
], ids=['dictionary', 'set'])
def test_container_flow_values_keep_independent_owners(tmp_path, target, body):
    source = tmp_path / 'flow.dewy'
    source.write_text('main=():>int64=>{let flag:bool=true\n' + body + '\n}\n')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target, debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target, debug_info=False)) == 0
    run = subprocess.run([cache_artifact(output).resolve()], timeout=10)
    assert run.returncode == 42
