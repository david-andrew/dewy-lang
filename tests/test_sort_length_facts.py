"""Sorting an `@` array by a write-free key keeps its length known."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'sort': ('''f=(@xs:array<int64>)=>{
    let n=xs.length
    xs.sort()
    if n >? 0 printl(xs[n-1])
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs)}''', '3\n'),
    'sort_key': ('''f=(@xs:array<int64>)=>{
    let n=xs.length
    xs.sort(key=(v:int64)=>-v)
    if n >? 0 printl(xs[n-1])
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs)}''', '1\n'),
    'sort_key_text': ('''f=(@xs:array<string>)=>{
    let n=xs.length
    xs.sort(key=(v:string)=>v.length reverse=true)
    if n >? 0 printl(xs[n-1])
}
main=()=>{let xs:array<string>=["bb" "a" "ccc"] f(@xs)}''', 'a\n'),
    'sort_named_key': ('''k=(v:int64):>int64=>v
f=(@xs:array<int64>)=>{
    let n=xs.length
    xs.sort(key=@k)
    if n >? 0 printl(xs[n-1])
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs)}''', '3\n'),
    'sort_with': ('''f=(@xs:array<int64>)=>{
    let n=xs.length
    xs.sort_with((a:int64 b:int64)=>a >? b)
    if n >? 0 printl(xs[n-1])
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs)}''', '1\n'),
    'sorted_key': ('''f=(xs:array<int64>)=>{
    let n=xs.length
    let ys=xs.sorted(key=(v:int64)=>-v)
    if n >? 0 printl(ys[n-1])
}
main=()=>f([3 1 2])''', '1\n'),
}
REJECTED = {
    # (the key changes the array it sorts)
    'key_mutates_local': '''main=()=>{
    let xs:array<int64>=[3 1 2]
    let n=xs.length
    xs.sort(key=(v:int64 $capture @xs)=>{xs.push(v) v})
    if n >? 0 printl(xs[n-1])
}''',
    'sorted_key_mutates_local': '''main=()=>{
    let xs:array<int64>=[3 1 2]
    let n=xs.length
    let ys=xs.sorted(key=(v:int64 $capture @xs)=>{xs.push(v); v})
    if n >? 0 printl(xs[n-1])
}''',
    # (the key writes a global the `@` parameter may be)
    'key_writes_global': '''let G:array<int64>=[3 1 2]
f=(@xs:array<int64>)=>{
    let n=xs.length
    xs.sort(key=(v:int64)=>{G.clear(); v})
    if n >? 0 printl(xs[n-1])
}
main=()=>f(@G)''',
    'named_key_writes_global': '''let G:array<int64>=[3 1 2]
k=(v:int64):>int64=>{G.clear(); v}
f=(@xs:array<int64>)=>{
    let n=xs.length
    xs.sort(key=@k)
    if n >? 0 printl(xs[n-1])
}
main=()=>f(@G)''',
    'less_writes_global': '''let G:array<int64>=[3 1 2]
f=(@xs:array<int64>)=>{
    let n=xs.length
    xs.sort_with((a:int64 b:int64)=>{G.clear(); a <? b})
    if n >? 0 printl(xs[n-1])
}
main=()=>f(@G)''',
    # (a key passed in has an unknown row)
    'key_parameter': '''f=(@xs:array<int64> k:(v:int64:>int64))=>{
    let n=xs.length
    xs.sort(key=@k)
    if n >? 0 printl(xs[n-1])
}''',
}


@pytest.mark.parametrize('name', PROVED)
def test_sort_length_facts_prove(compiler, tmp_path, name):
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
def test_sort_length_facts_reject(compiler, tmp_path, name):
    path = tmp_path / 'stale.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'index is in bounds' in checked.stdout + checked.stderr, checked.stdout + checked.stderr
