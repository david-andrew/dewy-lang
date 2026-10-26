"""Indexed shapes and mutable-result bounds require evidence at their use."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'nested_range': ('''R:type=[xs:array<int64>]
f=(@rs:array<R> j:int64)=>{
    if j <? 0 or j >=? rs.length return
    loop i in [0..rs[j].xs.length) {rs[j].xs[i]=1}
}
main=()=>{let rs=[R[[3 4]]] f(@rs 0) printl(rs[0].xs)}''', '[1 1]\n'),
    'array_range': ('''f=(@rs:array<array<int64>> j:int64)=>{
    if j <? 0 or j >=? rs.length return
    loop i in [0..rs[j].length) {rs[j][i]=1}
}
main=()=>{let rs:array<array<int64>>=[[3 4]] f(@rs 0) printl(rs[0])}''', '[1 1]\n'),
    'branch_limit': ('''f=(@xs:array<int64> n:int64)=>{
    let stop=if n <? xs.length n else xs.length
    loop i in [0..stop) {xs[i]=1}
}
main=()=>{let xs:array<int64>=[3 4] f(@xs 5) printl(xs)}''', '[1 1]\n'),
    'append_result': ('''mk=(@xs:array<int64>):>int64=>{xs.push(7) xs.length-1}
main=()=>{
    let xs:array<int64>=[]
    let i=mk(@xs)
    let j=mk(@xs)
    xs[i]=3
    printl(xs[i] xs[j])
}''', '3 7\n'),
    'append_field': ('''R:type=[xs:array<int64>]
mk=(@xs:array<int64>):>int64=>{xs.push(7) xs.length-1}
main=()=>{let r=R[[]] let i=mk(@r.xs) printl(r.xs[i])}''', '7\n'),
    'append_arms': ('''mk=(@xs:array<int64> b:bool):>int64=>{
    if b {xs.push(7) return xs.length-1}
    xs.push(8)
    xs.length-1
}
main=()=>{let xs:array<int64>=[] let i=mk(@xs false) printl(xs[i])}''', '8\n'),
}

REJECTED = {
    'inner_replace': '''R:type=[xs:array<int64>]
f=(@rs:array<R> j:int64)=>{
    if j <? 0 or j >=? rs.length return
    loop i in [0..rs[j].xs.length) {rs[j].xs=[] rs[j].xs[i]=1}
}''',
    'element_replace': '''R:type=[xs:array<int64>]
f=(@rs:array<R> j:int64)=>{
    if j <? 0 or j >=? rs.length return
    loop i in [0..rs[j].xs.length) {rs[j]=R[[]] rs[j].xs[i]=1}
}''',
    'inner_clear': '''R:type=[xs:array<int64>]
f=(@rs:array<R> j:int64)=>{
    if j <? 0 or j >=? rs.length return
    loop i in [0..rs[j].xs.length) {rs[j].xs.clear(); rs[j].xs[i]=1}
}''',
    'selector_change': '''R:type=[xs:array<int64>]
f=(@rs:array<R>)=>{
    if rs.length <? 2 return
    let j:int64=0
    loop i in [0..rs[j].xs.length) {j=1 rs[j].xs[i]=1}
}''',
    'append_clear': '''mk=(@xs:array<int64>):>int64=>{
    xs.push(7)
    let i=xs.length-1
    xs.clear();
    i
}
main=()=>{let xs:array<int64>=[] let i=mk(@xs) printl(xs[i])}''',
    'append_bad_arm': '''mk=(@xs:array<int64> b:bool):>int64=>{
    if b {xs.push(7) return xs.length-1}
    return 3
}
f=(b:bool)=>{let xs:array<int64>=[] let i=mk(@xs b) printl(xs[i])}''',
    'later_argument': '''mk=(@xs:array<int64> k:int64):>int64=>{xs.push(k) xs.length-1}
erase=(@xs:array<int64>):>int64=>{xs.clear(); 7}
main=()=>{
    let xs:array<int64>=[1 2]
    let j=mk(@xs erase(@xs))
    printl(xs[1] xs[j])
}''',
    'later_call': '''mk=(@xs:array<int64>):>int64=>{xs.push(7) xs.length-1}
erase=(@xs:array<int64>)=>{xs.clear();}
main=()=>{let xs:array<int64>=[] let i=mk(@xs) erase(@xs) printl(xs[i])}''',
    'no_guard': '''f=(xs:array<int64> i:int64):>int64=>xs[i]''',
}


PROVED.update({
    'nested_while': ('''R:type=[xs:array<int64>]
f=(@rs:array<R> j:int64)=>{
    if j <? 0 or j >=? rs.length return
    let n=rs[j].xs.length
    let i:int64=0
    loop i <? n {rs[j].xs[i]=1 i+=1}
}
main=()=>{let rs=[R[[3 4]]] f(@rs 0) printl(rs[0].xs)}''', '[1 1]\n'),
    'guard_across_call': ('''rewrite=(@xs:array<int64>)=>{loop i in [0..xs.length) {xs[i]=1}}
f=(@xs:array<int64> i:int64)=>{
    if i <? 0 or i >=? xs.length return
    rewrite(@xs)
    printl(xs[i])
}
main=()=>{let xs:array<int64>=[3 4] f(@xs 1)}''', '1\n'),
    'branch_shape': ('''R:type=[xs:array<int64>]
f=(@rs:array<R> j:int64 b:bool)=>{
    if j <? 0 or j >=? rs.length return
    let n=rs[j].xs.length
    let i:int64=0
    loop i <? n {
        if b {rs[j].xs[i]=1} else {rs[j].xs[i]=2}
        i+=1
    }
}
main=()=>{let rs=[R[[3 4]]] f(@rs 0 false) printl(rs[0].xs)}''', '[2 2]\n'),
})
REJECTED.update({
    'while_resize_backedge': '''R:type=[xs:array<int64>]
f=(@rs:array<R> j:int64)=>{
    if j <? 0 or j >=? rs.length return
    let n=rs[j].xs.length
    let i:int64=0
    loop i <? n {rs[j].xs[i]=1 rs[j].xs=[] i+=1}
}''',
    'helper_one_bad_arm': '''rewrite=(@xs:array<int64> b:bool)=>{
    if b {xs.clear(); return}
    loop i in [0..xs.length) {xs[i]=1}
}
f=(@xs:array<int64> i:int64 b:bool)=>{
    if i <? 0 or i >=? xs.length return
    rewrite(@xs b)
    printl(xs[i])
}''',
    'helper_callback': '''rewrite=(@xs:array<int64> callback:<(@ys:array<int64>):>void>)=>{callback(@xs)}
f=(@xs:array<int64> i:int64 callback:<(@ys:array<int64>):>void>)=>{
    if i <? 0 or i >=? xs.length return
    rewrite(@xs @callback)
    printl(xs[i])
}''',
    'helper_alias': '''rewrite=(@xs:array<int64> @ys:array<int64>)=>{
    loop i in [0..xs.length) {xs[i]=1}
    ys.clear();
}
f=(@xs:array<int64> i:int64)=>{
    if i <? 0 or i >=? xs.length return
    rewrite(@xs @xs)
    printl(xs[i])
}''',
})


@pytest.mark.core_quick
@pytest.mark.parametrize('name', PROVED)
def test_index_length_facts_prove(compiler, tmp_path, name):
    source, expected = PROVED[name]
    path = tmp_path / 'proof.dewy'
    path.write_text(source + '\n')
    checked = subprocess.run([compiler, 'check', '--obligations', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'runtime check:' not in checked.stdout
    for flags in ([], ['--release']):
        out = tmp_path / 'proof'
        built = subprocess.run([compiler, 'build', path, '-o', out, *flags], text=True, capture_output=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([out], text=True, capture_output=True, timeout=10)
        assert ran.returncode == 0 and ran.stdout == expected, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('name', REJECTED)
def test_index_length_facts_reject_stale(compiler, tmp_path, name):
    path = tmp_path / 'stale.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    expected = 'mutable arguments 1 and 2 overlap' if name == 'helper_alias' else 'index is'
    assert expected in checked.stdout + checked.stderr, checked.stdout + checked.stderr


@pytest.mark.parametrize('early', [False, True])
def test_place_summary_does_not_skip_cleanup(compiler, tmp_path, early):
    helper = tmp_path / 'helper.jo'
    helper.write_text('mk = (xs: mut int[]) -> int:\n'
                      '    xs.push(7)\n'
                      '    defer xs.clear()\n'
                      + ('    return ' if early else '    ') + 'xs.len() - 1\n')
    source = tmp_path / 'cleanup.dewy'
    source.write_text('from p"helper.jo" import mk\n'
                      'main=()=>{let xs:array<int64>=[] let i=mk(@xs) printl(xs[i])}\n')
    checked = subprocess.run([compiler, 'check', source], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'index is' in checked.stdout + checked.stderr, checked.stdout + checked.stderr
