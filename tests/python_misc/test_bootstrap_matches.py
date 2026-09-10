"""Source match arms share the native checker's ordinary flow machinery."""
import test_bootstrap_check as source_values

CASES = [
    'let choose=(x:int64|string y:int64|string):>int64=>match (x y) {(a:int64 b:int64)=>0 (a:string b:string)=>1 (_ _)=>42}\nchoose(1 "a")',
    'let choose=(x:int64|string y:int64|string):>int64=>match (x y) {(a:int64 b:int64)=>0 (a:string b:string)=>1 (a:int64 b:string)=>2 (_ _)=>42}',
    'Root=type of [x:int64]\nA=type of Root\nlet f=(v:Root):>int64=>match v {a:A=>a.x other:Root=>{other=A[2] other.x}}\nf(Root[1])',
    'let f=(p:[x:int64 y:int64=2]):>int64=>p.y\nf([1])',
    'let x:int64=2\nmatch x {<0>=>"zero" _=>"other"}',
    'let x:int64=2\nmatch x {<0>=>1 _=>1}',
    'let x=if true {1} else {2}\nx',
    'if true {1} else {2}',
    'if true {1} else {1}',
    'if true {"a"} else {"b"}',
    'let p=[x=1]\nmatch p {[x x]=>x}',
    'let x:int64|string=1\nmatch x {n:int64=>n s:string=>0}',
    'let x:int64|string=1\nmatch x {n:int64=>n _=>0}',
    'let f=(x:int64|string):>int64=>match x {n:int64=>n s:string=>s.length}\nf(1)',
    'let f=(x:int64?):>int64=>match x {n:int64=>n <none>=>0}\nf(1)',
    'let f=(x:int64):>int64=>match x {_=>x}\nf(1)',
    'let f=(x:int64):>int64=>match x {n:int64<n <? 0>=>0 n:int64<n >=? 0>=>n}\nf(1)',
    'let f=(x:int64):>int64=>match x {n:int64<n not=? 0>=>n <0>=>0}\nf(1)',
    'let f=(x:int64):>int64=>match x {<0>=>1 _=>2}\nf(1)',
    'let f=(x:int64):>int64=>match x {n:int64<n <? 0>=>0} else 1\nf(1)',
    'let f=(x:int64|string):>int64=>if false 7 else match x {n:int64=>n s:string=>s.length}\nf(1)',
    'let f=(x:int64|string):>int64=>match x {(n:int64)=>n (s:string)=>s.length}\nf(1)',
    'let f=(x:int64 y:string):>int64=>match (x y) {(n:int64 s:string)=>n+s.length}\nf(1 "a")',
    'let f=(x:int64 y:string):>int64=>match (x y) {(n:int64<n <? 0> s:string)=>0 (_ _)=>1}\nf(1 "a")',
    'let f=(x:int64):>int64=>x\nmatch f(2) {n:int64=>n}',
    'let p=[x=1 y="a"]\nmatch p {[x y]=>x+y.length}',
    'let f=(p:[x:int64]):>int64=>match p {[x:int64<x <? 0>]=>0 [x:int64<x >=? 0>]=>x}\nf([1])',
    'A=type of [x:int64]\nB=type of [y:string]\nlet f=(v:A|B):>int64=>match v {[x]=>x [y]=>y.length}\nf(A[1])',
    'Root=$abstract type of [x:int64]\nA=type of Root\nB=type of Root\nlet f=(v:Root):>int64=>match v {a:A=>a.x b:B=>b.x}\nf(A[1])',
    'Root=type of [x:int64]\nA=type of Root\nlet f=(v:Root):>int64=>match v {a:A=>a.x other:Root=>other.x}\nf(A[1])',
    'let f=(x:int64|string):>void=>{match x {n:int64=>{} s:string=>{return}} let y:int64=x}\nf(1)',
    'let f=(x:int64):>int64=>match x {copy=>copy}\nf(1)',
    'let x:int64=2\nmatch x {n:int64=>{let local=n local}}',
    'let x:int64=2\nmatch x {<int64>=>1}',
    'let x:int64=2\nmatch x {<0>=>1 _=>2}',
]
ERRORS = [
    'let choose=(x:int64|string y:int64|string):>int64=>match (x y) {(a:int64 b:int64)=>0 (a:string b:string)=>1}',
    'let choose=(x:int64|string y:int64|string):>int64=>match (x y) {(a:int64 _)=>0 (b:int64 s:string)=>1 (_ _)=>2}',
    'let choose=(x:int64|string y:int64|string):>int64=>match (x y) {(a:int64 s:string)=>0 (b:int64 t:string)=>1 (_ _)=>2}',
    'let x:int64=1\nmatch x {<0>=>{} _=>1}',
    'Root=$abstract type of [x:int64]\nA=type of Root\nlet f=(v:Root):>int64=>match v {a:A=>a.x}\nB=type of Root',
    # Hosted coverage of a guarded non-integer record field is conservative.
    'let f=(p:[x:int64|string]):>int64=>match p {[x:int64]=>x _=>0}\nf([1])',
    'let x:int64|string=1\nmatch x {n:int64=>n}',
    'let x:int64=1\nmatch x {<0>=>1}',
    'let x:int64=1\nmatch x {_=>1 <int64>=>2}',
    'let x:int64=1\nmatch x {<int64>=>1 <int64>=>2}',
    'let x:int64=1\nmatch x {n:int64<n <? 0>=>1 n:int64<n >? 0>=>2}',
    'let x:int64=1\nmatch x {}',
    'let x:int64=1\nmatch x {1}',
    'let x:int64=1\nmatch x {1=>2}',
    'let x:int64=1\nmatch x {<>=>2}',
    'let x:int64=1\nmatch x {<int64 string>=>2}',
    'let x:int64=1\nmatch x {n:int64=>n}; n',
    'let x:int64=1\nmatch x {(n:int64 s:string)=>n}',
    'let x:int64=1\nmatch (x x) {n:int64=>n}',
    'let x:int64=1\nmatch x {[missing]=>1}',
    'Root=type of [x:int64]\nA=type of Root\nlet f=(v:Root):>int64=>match v {a:A=>a.x}',
    'let p=[x=1]\nmatch p {[1]=>1}',
]


def test_native_match_source_values(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, validate_matches=True)
