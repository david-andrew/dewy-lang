"""Creating a closure writes nothing: only its calls run the body.

The facts transfer and the obligation slice keep what a closure's creation
cannot change; every call that can run the body (an indirect call, or a
callee whose summary calls a callback) still forgets what the body may write.
"""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVED = {
    'pure_sort_key': '''# pure sort key: creating it writes nothing
pick=(words:array<string>):>int64=>{
    let xs=[1 2 3]
    let ws=words
    ws.sort(key=(s:string)=>-bytes(s).length)
    return xs[2]
}
main=():>void=>exit(entry()) entry=():>int64=>pick(["a" "bb"])
''',
    'closure_never_called': '''# a closure that would write the index, made but never called
pick=():>int64=>{
    let xs=[1 2 3]
    let i=0
    let t=0
    let bump=($capture @i)=>{i=7}
    loop k in [0..3) {
        t+=xs[i]
    }
    return t
}
main=():>void=>exit(entry()) entry=():>int64=>pick()
''',
}

REJECTED = {
    'key_writes_capture': ('''# a key that writes a captured index: the sort's call runs it
pick=(words:array<string>):>int64=>{
    let xs=[1 2 3]
    let i=0
    let ws=words
    ws.sort(key=($capture @i s:string)=>{i=7 return -bytes(s).length})
    return xs[i]
}
main=():>void=>exit(entry()) entry=():>int64=>pick(["a" "bb"])
''', 'i may have changed at this call to sort'),
    'called_closure_writes_capture': ('''# a closure that writes a captured index, called later
pick=():>int64=>{
    let xs=[1 2 3]
    let i=0
    let bump=($capture @i)=>{i=7}
    let k=xs[i]
    bump()
    return k+xs[i]
}
main=():>void=>exit(entry()) entry=():>int64=>pick()
''', 'i may have changed at this call'),
    'callback_writes_captured_field': ('''# a closure that writes a captured record's field, passed to a direct call
Box:type=[at:int64 items:array<int64>]
twice=(f:<():>void>)=>{f() f()}
pick=():>int64=>{
    let b=Box[0 [1 2 3]]
    let move=($capture @b)=>{b.at=9}
    twice(@move)
    return b.items[b.at]
}
main=():>void=>exit(entry()) entry=():>int64=>pick()
''', 'cannot prove index is in bounds'),
    'closure_called_next_pass': ('''# a closure made in one pass of a loop and called in the next
pick=():>int64=>{
    let xs=[1 2 3]
    let i=0
    let t=0
    let bump=($capture @i)=>{i=7}
    loop k in [0..3) {
        t+=xs[i]
        bump()
    }
    return t
}
main=():>void=>exit(entry()) entry=():>int64=>pick()
''', 'i may have changed at this loop'),
}


def check(compiler, tmp_path, name, source):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=30,
                          env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'})


@pytest.mark.parametrize('name', PROVED)
def test_closure_creation_keeps_facts(compiler, tmp_path, name):
    result = check(compiler, tmp_path, name, PROVED[name])
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('name', REJECTED)
def test_closure_call_forgets_writes(compiler, tmp_path, name):
    source, message = REJECTED[name]
    result = check(compiler, tmp_path, name, source)
    assert result.returncode != 0
    assert message in result.stdout + result.stderr, result.stdout + result.stderr
