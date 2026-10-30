"""A helper returning an optional index carries its bounds to the present arm."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'best_index': ('''best=(xs:array<int>):>int?=>{
    if xs.is_empty return none
    let at=0
    loop i in [1..xs.length) if xs[i] >? xs[at] at=i
    at
}
main=()=>{
    let xs=[3 9 2]
    let c=best(xs)
    if c isnt? none printl(xs[c])
}''', '9\n'),
    'early_return_in_loop': ('''find=(xs:array<string> word:string):>int?=>{
    loop i in 0.. and x in xs if x =? word return i
    none
}
main=()=>{
    let words=["a" "b" "c"]
    let w=find(words "b")
    if w isnt? none printl(words[w])
    match find(words "c") {
        <none> => printl("none")
        k:int => printl(words[k])
    }
    if find(words "z") is? none printl("missing")
}''', 'b\nc\nmissing\n'),
    'guarded_last': ('''last=(xs:array<int>):>int?=>{
    if xs.length <? 2 return none
    xs.length-1
}
main=()=>{let xs=[4 5] let c=last(xs) if c isnt? none printl(xs[c])}''', '5\n'),
    'constant_payload': ('''first=(xs:array<int>):>int?=>{
    if xs.is_empty return none
    0
}
main=()=>{let ys=[7] let c=first([1 2]) if c isnt? none printl(ys[c])}''', '7\n'),
    'coalesce_present': ('''best=(xs:array<int>):>int?=>{
    if xs.is_empty return none
    xs.length-1
}
main=()=>{let xs=[3 9] printl(xs[best(xs) ?? 0])}''', '9\n'),
}

REJECTED = {
    # one past the end on a present return
    'past_end': '''f=(xs:array<int>):>int?=>{
    if xs.is_empty return none
    xs.length
}
main=()=>{let xs=[1 2] let c=f(xs) if c isnt? none printl(xs[c])}''',
    # every return is none: nothing describes a payload
    'only_none': '''f=(xs:array<int>):>int?=>none
main=()=>{let xs=[1 2] let c=f(xs) if c isnt? none printl(xs[c])}''',
    # the relation is to the argument, not another array
    'other_array': '''f=(xs:array<int>):>int?=>{
    if xs.is_empty return none
    xs.length-1
}
main=()=>{let xs=[1 2 3] let ys=[1] let c=f(xs) if c isnt? none printl(ys[c])}''',
    # the array changed after the call
    'shrunk_after': '''f=(xs:array<int>):>int?=>{
    if xs.is_empty return none
    xs.length-1
}
main=()=>{let xs=[1 2 3] let c=f(xs) xs.pop(); if c isnt? none printl(xs[c])}''',
    # a mutable argument cleared by the callee
    'shrunk_inside': '''f=(@xs:array<int>):>int?=>{
    if xs.is_empty return none
    let i=xs.length-1
    xs.clear()
    i
}
main=()=>{let xs=[1 2 3] let c=f(@xs) if c isnt? none printl(xs[c])}''',
    # an unrelated parameter's value
    'parameter_value': '''f=(xs:array<int> k:int):>int?=>{
    if k <? 0 return none
    k
}
main=()=>{let xs=[1 2] let c=f(xs 7) if c isnt? none printl(xs[c])}''',
    # an optional local whose payload may reach the length
    'optional_local': '''f=(xs:array<int>):>int?=>{
    if xs.is_empty return none
    let c:int?=xs.length-1
    if xs[0] >? 5 c=xs.length
    c
}
main=()=>{let xs=[1 2] let c=f(xs) if c isnt? none printl(xs[c])}''',
    # no test of the present arm
    'untested': '''f=(xs:array<int>):>int?=>{
    if xs.is_empty return none
    0
}
main=()=>{let xs:array<int>=[] printl(xs[f(xs) ?? 0])}''',
}


@pytest.mark.parametrize('name', PROVED)
def test_optional_index_summary_proves(compiler, tmp_path, name):
    source, expected = PROVED[name]
    path = tmp_path / 'proof.dewy'
    path.write_text(source + '\n')
    checked = subprocess.run([compiler, 'check', '--obligations', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'runtime check:' not in checked.stdout
    out = tmp_path / 'proof'
    built = subprocess.run([compiler, 'build', path, '-o', out], text=True, capture_output=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([out], text=True, capture_output=True, timeout=10)
    assert ran.returncode == 0 and ran.stdout == expected, ran.stdout + ran.stderr


@pytest.mark.parametrize('name', REJECTED)
def test_optional_index_summary_rejects(compiler, tmp_path, name):
    path = tmp_path / 'near.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'index is' in checked.stdout + checked.stderr, checked.stdout + checked.stderr
