"""Closed script storage and collection idioms preserve only shared evidence."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVED = {
    'script_sum': ('''let xs:array<int64>=[1 2 3]
let n=0
loop i in [0..xs.length) {n+=xs[i]}
printl(n)''', '6\n'),
    'script_call': ('''let xs:array<int64>=[3]
printl("ready")
printl(xs[0])''', 'ready\n3\n'),
    'script_dict': ('''let d:dict<string int64>=[]
let k="x"
d[k]=0
d[k]+=1
printl(d[k])''', '1\n'),
    'missing_dict_key': ('''main=()=>{let d:dict<string int64>=[];loop k in ["a" "a"] {if k not in? d d[k]=0;d[k]+=1;printl(d[k])}}''', '1\n2\n'),
    'division': ('''f=(w:string)=>{if w.length >=? 3 {let mid=w.length//2;printl(w[mid-1..mid+1])}}
f("abcde")''', 'bcd\n'),
    'scan': ('''f=(src:string)=>{let i=0;loop i <? src.length {let start=i;loop i <? src.length and src[i] =? "a" i+=1;printl(src[start..i));i+=1}}
f("aaabaa")''', 'aaa\naa\n'),
    'joinint': ('''f=(xs:array<float64>):>int64=>{let best=0;loop i in [1..xs.length) {if xs[i] >? xs[best] best=i};best}
printl(f([1.0 3.0]))''', '1\n'),
    'lastneq': ('''f=(xs:array<int64>)=>{loop i in [0..xs.length) {if i =? 0 or i =? xs.length-1 {} else printl(xs[i+1])}}
f([1 2 3])''', '3\n'),
    'namedstr': ('''HEX="0123456789abcdef"
f=(v:uint32)=>printl(HEX[v and 0xF])
f(10)''', 'a\n'),
    'literals': ('''let xs:array<int64>=[]
loop x in [1 2 3] xs.push(x)
printl(xs)''', '[1 2 3]\n'),
    'word': ('''loop w in ["apple" "banana"] printl(w[0])''', 'a\nb\n'),
    'whitespace_words': ('''f=(s:string)=>{loop w in s.split() printl(w[0])}
f("hello  world")''', 'h\nw\n'),
    'grow_bounds': ('''f=(xs:array<int64>)=>{let s:array<int>=[0];loop x in xs s.push(s[s.length-1]+x);printl(s)}
f([1 2 3])''', '[0 1 3 6]\n'),
}

PROVED['snapshot_replaced'] = ('let words:array<string>=["abcdef"]\nloop w in words {\n    if w.length >=? 3 {\n        words[0]=""\n        let mid=w.length//2\n        printl(w[mid])\n    }\n}\n', 'd\n')
PROVED['global_array_accumulator'] = ('''let grid:array<array<int64>>=[[1 2] [3 4]]
loop row in grid {
    let n:int64=0
    loop x in row n+=x
    printl(n)
}''', '3\n7\n')

PROVED['modulo_loop'] = ('f=(xs:array<uint8>):>uint32=>{let a:uint32=1;let b:uint32=0;loop x in xs {a=(a+x)%65521;b=(b+a)%65521};(b<<16)|a}\nprintl(f([1 2]))', '393220\n')

REJECTED = {
    'function_write': '''let xs:array<int64>=[3]
clear=()=>{xs=[]}
clear()
printl(xs[0])''',
    'callback_write': '''let xs:array<int64>=[3]
clear=()=>{xs=[]}
let f=@clear
f()
printl(xs[0])''',
    'mutable_argument': '''clear=(@xs:array<int64>)=>{xs=[]}
let xs:array<int64>=[3]
clear(@xs)
printl(xs[0])''',
    'dict_argument': '''clear=(@d:dict<string int64>)=>{d=[]}
let d:dict<string int64>=[]
d["x"]=1
clear(@d)
printl(d["x"])''',
    'one_arm_key': '''main=()=>{let d:dict<string int64>=[];let k="b";if k =? "a" d[k]=0;printl(d[k])}''',
    'scan_overshoot': '''f=(src:string)=>{let i=0;loop i <? src.length {let start=i;loop i <? src.length and src[i] =? "a" i+=2;printl(src[start..i));i+=1}}
f("aaa")''',
    'division_short': '''f=(w:string)=>{if w.length >=? 2 {let mid=w.length//2;printl(w[mid+1])}}
f("ab")''',
    'division_one': '''f=(w:string)=>{if w.length >=? 3 {let mid=w.length//1;printl(w[mid+1])}}
f("abc")''',
    'changed_string': '''HEX="0123456789abcdef"
f=(v:uint32)=>printl(HEX[v and 0xF])
HEX=""
f(10)''',
    'literal_outlier': '''let xs:array<int8>=[]
loop x in [1 2 128] xs.push(x)''',
    'literal_empty': '''loop w in ["apple" ""] printl(w[0])''',
    'argmax_bad_entry': '''f=(xs:array<float64>):>int64=>{let best=100;loop i in [1..xs.length) {if xs[i] >? xs[best] best=i};best}
printl(f([1.0 3.0]))''',
    'words_replaced': '''main=()=>{let ws="a b".split();ws[0]="";loop w in ws printl(w[0])}''',
    'words_delimiter': '''loop w in "a,,b".split(",") printl(w[0])''',
    'grow_clear': '''f=(xs:array<int64>)=>{let s:array<int>=[0];loop x in xs {s.clear();s.push(s[s.length-1]+x)};printl(s)}
f([1])''',
    'grow_pop': '''f=(xs:array<int64>)=>{let s:array<int>=[0];loop x in xs {s.pop();s.push(s[s.length-1]+x)};printl(s)}
f([1])''',
}


REJECTED.update({'modulo_entry': 'f=(xs:array<uint8>):>uint32=>{let b:uint32=70000;loop x in xs b=(b+x)%65521;b<<16}\nprintl(f([]))', 'modulo_other_store': 'f=(xs:array<uint8>):>uint32=>{let b:uint32=0;loop x in xs {b=(b+x)%65521;if x =? 1 b=70000};b<<16}\nprintl(f([1]))', 'modulo_mutation': 'change=(@b:uint32)=>{b=70000}\nf=(xs:array<uint8>):>uint32=>{let b:uint32=0;loop x in xs {b=(b+x)%65521;change(@b)};b<<16}\nprintl(f([1]))', 'argmax_mutation': 'change=(@i:int)=>{i=100}\nf=(xs:array<float64>):>int64=>{let best=0;loop i in [1..xs.length) {best=i;change(@best);printl(xs[best])};best}\nprintl(f([1.0 3.0]))'})

@pytest.mark.parametrize('name', PROVED)
@pytest.mark.parametrize('release', [False, True])
def test_script_fact_proved(compiler, tmp_path, name, release):
    source = tmp_path / 'main.dewy'
    source.write_text(PROVED[name][0])
    binary = tmp_path / 'program'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == PROVED[name][1]


@pytest.mark.parametrize('name', REJECTED)
def test_script_fact_rejected(compiler, tmp_path, name):
    source = tmp_path / 'main.dewy'
    source.write_text(REJECTED[name])
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert checked.returncode != 0
    assert 'cannot prove' in checked.stderr or 'not in bounds' in checked.stderr, checked.stderr
