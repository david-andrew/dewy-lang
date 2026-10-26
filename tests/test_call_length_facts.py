"""Call-stable const values and length relations belong to evaluated values."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'const_loop': ('''const NAMES=["a" "b"]
f=(j:int64)=>{printl(j)}
main=()=>{loop j in [0..NAMES.length) {f(j) printl(NAMES[j])}}''', '0\na\n1\nb\n'),
    'const_element_callback': ('''const NAMES=["a" "b"]
f=(i:int64 g:<(n:int64):>void>)=>{
    if i <? 0 or i >=? NAMES.length return
    if NAMES[i].length <? 1 return
    g(i)
    printl(NAMES[i][0])
}
main=()=>f(1 (n:int64)=>{printl(n)})''', '1\nb\n'),
    'const_copy': ('''const NAMES=["a" "b"]
f=()=>{let xs=NAMES; xs.clear(); printl(xs.length)}
main=()=>{loop j in [0..NAMES.length) {f(); printl(NAMES[j])}}''', '0\na\n0\nb\n'),
    'search_fallback': ('''f=(xs:array<int64> v:int64):>int64=>{
    let i=xs.index_of(v) ?? -1
    if i >=? 0 return xs[i]
    return 0
}
main=()=>{printl(f([4 7] 7) f([4 7] 2) f([] 2))}''', '7 0 0\n'),
    'text_search_slice': ('''f=(s:string part:string):>string=>{
    let i=s.find(part) ?? -1
    if i >=? 0 return s[i..]
    return "missing"
}
main=()=>{printl(f("abc" "b") f("abc" "z"))}''', 'bc missing\n'),
    'chars': ('''f=(s:string):>int=>{
    let cs=s.chars()
    let n:int=0
    loop i in [0..s.length) {if cs[i] =? s[i] n+=1}
    n
}
main=()=>printl(f("é\\r\\n🇺🇸👩‍💻") f(""))''', '4 0\n'),
    'sorted': ('''f=(xs:array<int64>)=>{
    let ys=xs.sorted()
    loop i in [0..xs.length) printl(ys[i])
}
main=()=>{f([3 1 2]) f([])}''', '1\n2\n3\n'),
    'sorted_key': ('''f=(xs:array<int64>)=>{
    let ys=xs.sorted(key=(v:int64)=>v)
    loop i in [0..xs.length) printl(ys[i])
}
main=()=>f([3 1 2])''', '1\n2\n3\n'),
    'int_store_guard': ('''f=(@xs:array<int64> i:int)=>{
    if i <? 0 or i >=? xs.length return
    xs[i]=9
}
main=()=>{let xs:array<int64>=[1 2] f(@xs 1) printl(xs)}''', '[1 9]\n'),
}
REJECTED = {
    'mutable_global': '''let NAMES:array<string>=["a" "b"]
f=()=>{NAMES.clear();}
main=()=>{loop j in [0..NAMES.length) {f(); printl(NAMES[j])}}''',
    'changed_copy': '''const NAMES=["a" "b"]
main=()=>{let xs=NAMES; xs.clear(); loop j in [0..NAMES.length) printl(xs[j])}''',
    'search_zero_empty': '''f=(xs:array<int64> v:int64):>int64=>{
    let i=xs.index_of(v) ?? 0
    return xs[i]
}''',
    'search_changed_array': '''f=(@xs:array<int64> v:int64):>int64=>{
    let i=xs.index_of(v) ?? -1
    xs.clear();
    if i >=? 0 return xs[i]
    return 0
}''',
    'text_search_end': '''f=(s:string part:string):>string=>{
    let i=s.find(part) ?? -1
    if i >=? 0 return s[i]
    return "missing"
}''',
    'chars_changed_text': '''f=(s:string)=>{
    let cs=s.chars()
    let other="{s}extra"
    loop i in [0..other.length) printl(cs[i])
}''',
    'chars_shrunk': '''f=(s:string)=>{
    let cs=s.chars(); cs.clear();
    loop i in [0..s.length) printl(cs[i])
}''',
    'sorted_shrunk': '''f=(xs:array<int64>)=>{
    let ys=xs.sorted(); ys.clear();
    loop i in [0..xs.length) printl(ys[i])
}''',
    'int_store_unbounded': '''f=(@xs:array<int64> i:int)=>{xs[i]=1}''',
    'int_store_huge': '''f=(@xs:array<int64> i:int)=>{if i <=? 72057594037927935 return; xs[i]=1}''',
}


@pytest.mark.core_quick
@pytest.mark.parametrize('name', PROVED)
def test_call_length_facts_prove(compiler, tmp_path, name):
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
def test_call_length_facts_reject(compiler, tmp_path, name):
    path = tmp_path / 'stale.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'index is' in checked.stdout + checked.stderr, checked.stdout + checked.stderr
    if name.startswith('int_store_'):
        assert 'conversion to int64' not in checked.stdout + checked.stderr


def test_imported_const_retains_guard(compiler, tmp_path):
    (tmp_path / 'names.dewy').write_text('const NAMES=["a" "b"]\n')
    path = tmp_path / 'user.dewy'
    path.write_text('import p"names.dewy" as names\n'
                    'f=(g:<(n:int64):>void>)=>{loop i in [0..names.NAMES.length) {g(i); printl(names.NAMES[i])}}\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr


@pytest.mark.parametrize('change', ['NAMES.clear()', 'NAMES[0]="x"', 'erase(@NAMES)'])
def test_const_has_no_mutable_route(compiler, tmp_path, change):
    path = tmp_path / 'const.dewy'
    path.write_text('const NAMES=["a" "b"]\n'
                    'erase=(@xs:array<string>)=>{xs.clear();}\n'
                    f'main=()=>{{{change};}}\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'cannot modify const' in checked.stderr, checked.stdout + checked.stderr


def test_jo_graphemes_do_not_equal_byte_length(compiler, tmp_path):
    (tmp_path / 'bytes.jo').write_text('f = (s: str):\n'
                                      '    cs = graphemes(s)\n'
                                      '    static_assert(cs.len() == s.len())\n')
    path = tmp_path / 'user.dewy'
    path.write_text('from p"bytes.jo" import f\nmain=()=>f("é")\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'assert' in checked.stdout + checked.stderr, checked.stdout + checked.stderr
