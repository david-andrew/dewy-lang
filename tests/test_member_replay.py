"""Per-member typing and proof results survive checked-body replay, including fallbacks."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tools.compiler.member_replay_diff import compare


SOURCES = {
    'later_debug_name': '''
$runtime_checks
U:type='aa'|'bbb'
make=(text:string):>dict<string U>=>{
    let table:dict<string U>=[]
    loop s in members(U) {table[s]=s}
    let converted:U=text
    table["converted"]=converted
    return table
}
printl(make("aa"))
''',
    'narrowed_path': '''
$runtime_checks
Box:type=[value:array<string>|none]
make=(box:Box)=>{
    let table:dict<string string>=[]
    if box.value isnt? none {
        loop s in members('aa'|'bbb') {table[s]=box.value[0]}
    }
    return table
}
printl(make(Box[value=["x"]]))
''',
    'inferred_text': '''
$runtime_checks
make=()=>{
    let prefix="aa"
    let table:dict<string 'aa'|'bbb'>=[]
    loop s in members('aa'|'bbb') {table[s]=prefix}
    return table
}
printl(make())
''',
    'tables': '''
U:type='aa'|'bbb'
make=():>dict<string U>=>{
    let table:dict<string U>=[]
    loop s in members(U) {table[s]=s}
    return table
}
printl(make())
''',
    'punctuation_like': '''
make=()=>{
    let table:dict<uint8 array<string>>=[]
    loop s in members('aa'|'ab'|'!!'|'???') {
        let raw=bytes(s)
        $runtime_assert raw.length >? 0
        let first=raw[0]
        let letter=b'a' <=? first <=? b'z'
        if not letter {
            if first in? table table[first].push(s) else table[first]=[s]
        }
    }
    return table
}
printl(make())
''',
    'open_proofs': '''
loop s in members('aa'|'bbb') {
    let raw=bytes(s)
    $assert raw.length >? 1
    let first=raw[0]
    $assert first >=? 0
}
''',
    'later_proof_fails': '''
loop s in members('aa'|'bbb') {
    let raw=bytes(s)
    $assert raw.length <? 3
}
''',
    'singleton_proof': "loop s in members('aa'|'bbb') {$assert bytes(s).length >? 1}",
    'singleton_overloads': '''
pick=((s:'aa'):>int64=>1)&((s:'bbb'):>int64=>2)&((s:string):>int64=>3)
loop s in members('aa'|'bbb') {printl(pick(s))}
''',
    'later_conversion_fails': '''
U:type='aa'|'bbb'
make=()=>{
    let table:dict<string 'aa'>=[]
    loop s in members(U) {table[s]=s}
    return table
}
printl(make())
''',
    'constant_diagnostic_order': '''
loop s in members('a'|'bb') {$runtime_assert s =? "a"}
printl(unknown)
''',
    'literal_transform': '''
make=()=>{
    let table:dict<string string>=[]
    loop s in members('aa'|'bbb') {table["{s}!"]=s}
    return table
}
printl(make())
''',
    'narrow_and_jump': '''
loop s in members('aa'|'bbb') {
    if s =? 'aa' {continue}
    printl(s)
}
''',
    'unicode': '''
loop s in members('é'|'hello'|'💧') {
    let raw=bytes(s)
    $runtime_assert raw.length >? 0
    let first=raw[0]
    $assert first >=? 0
}
''',
}
REJECTED = {'later_proof_fails', 'singleton_overloads', 'later_conversion_fails',
            'constant_diagnostic_order'}


@pytest.mark.parametrize('name', SOURCES)
@pytest.mark.parametrize('mode', ['native', 'release', 'g', 'wasm32'])
def test_member_replay_matches_reference(compiler, tmp_path, name, mode):
    source = tmp_path / f'{name}.dewy'
    source.write_text(SOURCES[name])
    same, accepted = compare(compiler, source, mode, tmp_path / 'comparison')
    assert same, f'{name}: diagnostics or emitted files differ; see {tmp_path}'
    assert accepted == (name not in REJECTED)


def test_member_replay_is_exercised(compiler, tmp_path):
    source = tmp_path / 'members.dewy'
    source.write_text(SOURCES['tables'] + SOURCES['open_proofs'] + SOURCES['punctuation_like'].replace('make', 'punctuation'))
    run = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'program'],
                         env=os.environ | {'DEWY_MEMBERS': 'trace', 'DEWY_EMIT_WORKERS': '1'},
                         capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert sum(': true,' in line for line in run.stderr.splitlines()
               if line.startswith('member template ')) == 3, run.stderr
