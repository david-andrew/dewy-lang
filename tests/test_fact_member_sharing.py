"""A members(U) block's facts are decided once for every copy, or else copy by copy, with the same answers."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PUNCTUATION = '''
make=()=>{
    let table:dict<uint8 array<string>>=[]
    loop s in members('aa'|'ab'|'!!'|'???'|'x'|'(') {
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
'''

# name: (source, decided once for all copies; None: a runtime-checked body is not decided)
SOURCES = {
    'shared': (PUNCTUATION, True),
    # (the block's own state after it: its copies' pushes)
    'later_state': ('''
make=()=>{
    let xs:array<string>=["x"]
    loop s in members('a'|'bb'|'ccc') {xs.push(s)}
    return xs[3]
}
printl(make())
''', False),
    # (each literal's own length proves it)
    'literal_lengths': ('''
make=()=>{
    let table:dict<string uint8>=[]
    loop s in members('aa'|'bbb'|'cc') {
        let raw=bytes(s)
        table[s]=raw[1]
    }
    return table
}
printl(make())
''', False),
    'one_copy_fails': ('''
make=()=>{
    let table:dict<string uint8>=[]
    loop s in members('aa'|'b'|'cc') {
        let raw=bytes(s)
        table[s]=raw[1]
    }
    return table
}
printl(make())
''', False),
    'one_copy_checked': ('''
$runtime_checks
make=()=>{
    let table:dict<string uint8>=[]
    loop s in members('aa'|'b'|'cc') {
        let raw=bytes(s)
        table[s]=raw[1]
    }
    return table
}
printl(make())
''', None),
}


def run(compiler, source, members, *args):
    env = os.environ | {'DEWY_MEMBERS': members, 'DEWY_EMIT_WORKERS': '1'}
    done = subprocess.run([compiler, *args, source], cwd=source.parent, env=env,
                          capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout, done.stderr


@pytest.mark.parametrize('name', SOURCES)
def test_member_facts_match_reference(compiler, tmp_path, name):
    text, shared = SOURCES[name]
    source = tmp_path / f'{name}.dewy'
    source.write_text(text)
    for args in (['check', '--obligations'], ['run']):
        assert run(compiler, source, '', *args) == run(compiler, source, 'reference', *args), (name, args)
    traced = run(compiler, source, 'trace', 'check')[2]
    decisions = [line for line in traced.splitlines() if line.startswith('member facts ')]
    if shared is None:
        assert decisions == [], traced
        return
    expected = f'{name}.dewy:2:10: 1 blocks, ' + ('shared' if shared else 'decided again')
    assert len(decisions) == 1 and decisions[0].endswith(expected), traced
