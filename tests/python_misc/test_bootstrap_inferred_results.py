"""Implicit results, explicit returns, and inferred parameter predicates."""
import test_bootstrap_check as source_values

CASES = [
    'Positive:type=int64<x=>x >? 0>\nlet f=():>Positive=>{return 1}\nf()',
    'Positive:type=int64<x=>x >? 0>\nlet f=():>Positive=>1\nf()',
    'let f=(x)=>x',
    'let f=(x)=>true',
    'let f=()=>[x=1]\nf()',
    'let f=()=>42\nf()',
    'let f=(x:int64)=>x+1\nf(2)',
    'let f=(x:int64)=>{x+1}\nf(2)',
    'let f=(x:int64)=>{return x+1}\nf(2)',
    'let f=(flag:bool)=>{if flag return 1 return 2}\nf(true)',
    'let f=()=>{}\nf()',
    'let f=()=>{return}\nf()',
    'let f=(flag:bool)=>{if flag return}\nf(true)',
    'let f=(flag:bool)=>if flag 1 else 2\nf(true)',
    'let f=(flag:bool)=>if flag "a" else "b"\nf(true)',
    'let f=(x:int64)=>{let g=()=>x+1 g()}\nf(2)',
    'let f=(x:int64)=>{let g=()=>{return x+1} g()}\nf(2)',
    'let f=(x:int64=2)=>x+1\nf()',
    'let f=(x=2)=>x+1\nf()',
    'let f=()=>{$expect true}\nf()',
    'let test=(v:int64|string)=>v is? int64\nlet use=(v:int64|string):>int64=>if test(v) v+1 else 0\nuse(2)',
    'let test=(v:int64|string)=>{v is? int64}\nlet use=(v:int64|string):>int64=>if test(v=v) v+1 else 0\nuse(2)',
    'let test=(v:int64|string)=>v isnt? string\nlet use=(v:int64|string):>int64=>if test(v) v+1 else 0\nuse(2)',
    'let test=(v:int64|string)=>v is? string\nlet use=(v:int64|string):>int64=>{if test(v) return 0 return v+1}\nuse(2)',
    'let positive=(x:int64)=>x >? 0',
    'let positive=(x:int64)=>0 <? x',
    'let ordered=(x:int64 y:int64)=>x <=? y',
    'let equal_length=(x:string y:string)=>x.length =? y.length',
    'let nonempty=(x:array<int64>)=>x.length >? 0',
    'let unrelated=(x:int64)=>true',
    'Root=$abstract type of [x:int64]\nA=type of Root\nlet choose=(flag:bool root:Root child:A)=>{if flag return root return child}',
]
ERRORS = [
    'let f=(flag:bool)=>{if flag return 1}',
    'let f=(flag:bool)=>{if flag return 1 return}',
    'let f=(flag:bool)=>{if flag return return 1}',
    'let f=()=>{1 return 2}',
    'let f=()=>{let g=()=>{return} 1 return 2}',
    'let f=(flag:bool)=>{if flag return 1 2}',
    'let f=(x:int64)=>f(x)',
    'f()\nlet f=()=>1',
    'let f=()=>{$expect true return 1}',
    'let f=()=>{$expect true 1}',
    'return 1',
    'let f=(flag:bool)=>{let g=()=>{return} if flag return 1}',
]


def test_native_inferred_function_results(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
