"""Demanded branch results and scan exits carry checked relational evidence."""
import re
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


SEARCH = """search=(xs:array<int64> needle:int64):>int64=>{
 let n=xs.length let i:int64=0
 loop i <? n {if xs[i] =? needle {return i};i+=1}
 -1
}
"""

PROVED = {
    'library_search': '''pick=(xs:array<int64>):>int64=>{
 let i=xs.index_of(3)
 if i is? Missing {return 0}
 xs[i]
}
main=()=>printl(pick([2 3]))
''',
    'search_result': SEARCH + '''pick=(xs:array<int64> needle:int64):>int64=>{
 let i=search(xs needle)
 if i >=? 0 {return xs[i]}
 0
}
main=()=>printl(pick([2 3] 3))
''',
    'refined_place_cursor': '''R:type=[b:array<uint8> at:int64<i => i >=? 0>]
pick=(@r:R):>uint8=>{
 if r.at <? r.b.length {return r.b[r.at]}
 0
}
main=()=>{let r:R=[[3] 0];printl(pick(@r))}
''',
    'conditional_bound': '''pick=(xs:array<int64>):>int64=>{
 let n=xs.length
 let stop=if n <? 12 n else 12
 if stop =? 0 return 0
 return xs[stop-1]
}
main=()=>printl(pick([1 2 3]))
''',
    'conditional_snapshot': '''pick=(xs:array<int64>):>int64=>{
 let n=xs.length
 let stop=if n <? 12 n else 12
 n=100
 if stop =? 0 return 0
 return xs[stop-1]
}
main=()=>printl(pick([1 2 3]))
''',
    'scanner_exit': '''scan=(b:array<uint8>):>int64=>{
 let n=b.length let i:int64=0
 loop i <? n {
  let j=i+1
  loop j <? n and b[j] not=? 10 {j+=1}
  $assert(j <=? n)
  i=j
 }
 i
}
main=()=>printl(scan([1 2 3]))
''',
    'split_last': '''last=(s:string):>string=>{
 let parts=s.split("/")
 parts[parts.length-1]
}
main=()=>{printl(last(""));printl(last("a/b"))}
''',
    'split_limited': '''last=(s:string limit:int64):>string=>{
 let parts=s.split("/" limit)
 parts[parts.length-1]
}
main=()=>{printl(last("a/b" -1));printl(last("a/b" 0))}
''',
    'empty_guard': '''pick=(xs:array<int64>):>int64=>{
 if xs.is_empty {return 0}
 xs[0]
}
main=()=>printl(pick([3]))
''',
    'place_cursor': '''R:type=[b:array<uint8> at:int64]
pick=(@r:R):>uint8=>{
 if r.at <? 0 {return 0}
 if r.at <? r.b.length {return r.b[r.at]}
 0
}
main=()=>{let r:R=[[3] 0];printl(pick(@r))}
''',
}

REJECTED = {
    'library_search_wrong_source': '''pick=(xs:array<int64> ys:array<int64>):>int64=>{
 let i=xs.index_of(3)
 if i is? Missing {return 0}
 ys[i]
}
main=()=>printl(pick([2 3] []))''',
    'library_search_replaced_source': '''pick=(xs:array<int64>):>int64=>{
 let ys=xs
 let i=ys.index_of(3)
 ys.clear()
 if i is? Missing {return 0}
 ys[i]
}
main=()=>printl(pick([2 3]))''',
    'library_search_missing_reachable': '''pick=(xs:array<int64>):>int64=>{
 let i=xs.index_of(3)
 if i is? Missing {$assert(false);return 0}
 xs[i]
}
main=()=>printl(pick([]))''',
    'search_replaced_source': SEARCH + '''pick=(xs:array<int64> needle:int64):>int64=>{
 let ys=xs
 let i=search(ys needle)
 ys.clear()
 if i >=? 0 {return ys[i]}
 0
}
main=()=>printl(pick([2 3] 3))''',
    'search_wrong_source': SEARCH + '''pick=(xs:array<int64> ys:array<int64> needle:int64):>int64=>{
 let i=search(xs needle)
 if i >=? 0 {return ys[i]}
 0
}
main=()=>printl(pick([2 3] [] 3))''',
    'one_bad_arm': '''pick=(xs:array<int64> flag:bool):>int64=>{
 let stop=if flag xs.length else 12
 if stop =? 0 return 0
 xs[stop-1]
}
main=()=>printl(pick([3] false))''',
    'changed_array': '''pick=(xs:array<int64>):>int64=>{
 let ys=xs
 let stop=if ys.length <? 12 ys.length else 12
 ys.clear()
 if stop =? 0 return 0
 ys[stop-1]
}
main=()=>printl(pick([3]))''',
    'scan_overshoot': '''scan=(b:array<uint8>):>int64=>{
 let n=b.length let j:int64=0
 loop j <? n and b[j] not=? 10 {j+=2}
 $assert(j <=? n)
 j
}
main=()=>printl(scan([3]))''',
    'empty_separator': '''last=(s:string):>string=>{
 let parts=s.split("")
 parts[parts.length-1]
}
main=()=>printl(last(""))''',
    'whitespace_split': '''last=(s:string):>string=>{
 let parts=s.split()
 parts[parts.length-1]
}
main=()=>printl(last(""))''',
    'unknown_separator': '''last=(s:string sep:string):>string=>{
 let parts=s.split(sep)
 parts[parts.length-1]
}
main=()=>printl(last("" ""))''',
    'pop_after_guard': '''pick=(xs:array<int64>):>int64=>{
 let ys=xs
 if ys.is_empty {return 0}
 ys.pop();ys[0]
}
main=()=>printl(pick([3]))''',
    'negative_place_cursor': '''R:type=[b:array<uint8> at:int64]
pick=(@r:R):>uint8=>{
 if r.at <? r.b.length {return r.b[r.at]}
 0
}
main=()=>{let r:R=[[3] -1];printl(pick(@r))}''',
}


@pytest.mark.parametrize('name', PROVED)
@pytest.mark.parametrize('release', [False, True])
def test_idiomatic_result_proved(compiler, tmp_path, name, release):
    source = tmp_path / f'{name}.dewy'
    source.write_text(PROVED[name])
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    # Inspect the caller, excluding the library split implementation's checks.
    if name in ('conditional_bound', 'empty_guard', 'place_cursor'):
        functions = re.split(r'(?m)^fn ', built.stdout)
        body = next((f for f in functions if f.startswith('f_pick_')), '')
        if release and not body:
            body = next((f for f in functions if f.startswith('f_main_')), '')
        assert body, built.stdout
        assert '__panic_bounds' not in body, body
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == {'split_last': '\nb\n', 'split_limited': 'b\na/b\n'}.get(name, '3\n')


@pytest.mark.parametrize('name', REJECTED)
def test_idiomatic_result_rejected(compiler, tmp_path, name):
    source = tmp_path / f'{name}.dewy'
    source.write_text(REJECTED[name])
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert checked.returncode != 0
    assert any(message in checked.stderr for message in ('cannot prove', 'not in bounds', 'assertion refuted')), checked.stderr


def test_clamped_byte_slice_keeps_utf8_obligation(compiler, tmp_path):
    source = tmp_path / 'slice.dewy'
    source.write_text('''$runtime_checks
prefix=(s:string):>string=>{
 let n=(s as array<uint8>).length
 s.byte_slice(0 if n <? 12 n else 12)
}
main=()=>printl(prefix("sample"))
''')
    checked = subprocess.run([compiler, 'check', '--obligations', source], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    assert 'char boundary' in checked.stdout
    assert 'slice is in bounds' not in checked.stdout


@pytest.mark.parametrize('source,expected', [
    ('''digit=(n:int64):>string=>{
 let hex="0123456789abcdef"
 let i=n%16
 hex.byte_slice(i i+1)
}
main=()=>printl(digit(10))''', 'a\n'),
    ('''scan=(b:array<uint8> start:int64):>int64=>{
 if start <? 0 or start >=? b.length {return 0}
 let j=start+1
 loop j <? b.length and b[j] not=? 10 {j+=1}
 $assert(start <? j)
 j
}
main=()=>printl(scan([3 4 5] 0))''', '3\n'),
])
def test_idiomatic_text_and_scan(compiler, tmp_path, source, expected):
    path = tmp_path / 'text.dewy'
    path.write_text(source)
    ran = subprocess.run([compiler, '--release', path], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == expected


@pytest.mark.parametrize('source', [
    # A foreign string may contain ASCII followed by a stray continuation byte.
    '''cut=(s:string):>string=>{
 let b=s as array<uint8>
 loop i in [0..b.length) {if b[i] =? b'-' {return s.byte_slice(i+1 b.length)}}
 ""
}
main=()=>printl(cut("x-é"))''',
    '''cut=(s:string):>string=>{
 let b=s as array<uint8>
 loop i in [0..b.length) {if b[i] =? 0xc3 {return s.byte_slice(i+1 b.length)}}
 ""
}
main=()=>printl(cut("é"))''',
    '''cut=(s:string):>string=>{
 let text="ascii"
 text=s
 text.byte_slice(1 2)
}
main=()=>printl(cut("é"))''',
    '''scan=(b:array<uint8> start:int64):>int64=>{
 if start <? 0 or start >=? b.length {return 0}
 let j=start+1
 loop j <? b.length {j-=1;break}
 $assert(start <? j)
 j
}
main=()=>printl(scan([3 4 5] 0))''',
])
def test_idiomatic_text_and_scan_reject(compiler, tmp_path, source):
    path = tmp_path / 'bad.dewy'
    path.write_text(source)
    ran = subprocess.run([compiler, 'check', path], capture_output=True, text=True)
    assert ran.returncode != 0
    assert 'cannot prove' in ran.stderr or 'not in bounds' in ran.stderr, ran.stderr


def test_library_search_empty_input(compiler, tmp_path):
    path = tmp_path / 'empty_search.dewy'
    path.write_text(PROVED['library_search'].replace('pick([2 3])', 'pick([])'))
    ran = subprocess.run([compiler, path], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout == '0\n', ran.stderr
