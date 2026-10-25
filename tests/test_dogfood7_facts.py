"""Round-seven idioms compose under no-traps; stale facts still reject."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'lock_fields': ('''
S:type=[count:int64 total:int64]
main=()=>{
    let init:dict<string S>=["a"->S[2 10] "b"->S[0 0]]
    let m=mutex(init)
    let table=@(m.lock())
    let rows=[loop [key st] in table [key=key st=st]]
    loop r in rows {
        if r.st.count =? 0 continue
        printl(r.st.total/r.st.count)
    }
}''', '5\n'),
    'lock_counting': ('''
S:type=[count:int64]
H:type=[path:string]
bump=(@table:dict<string S> hit:H):>void=>{
    if hit.path not in? table table[hit.path]=S[0]
    table[hit.path].count += 1
}
main=()=>{
    let m=mutex(dict<string S>[])
    let table=@(m.lock())
    let k="a"
    if k not in? table table[k]=S[0]
    table[k].count += 1
    bump(@table H[k])
    if k in? table printl(table[k].count)
}''', '2\n'),
    'lock_loop_counting': ('''
S:type=[count:int64]
main=()=>{
    let m=mutex(dict<string S>[])
    let table=@(m.lock())
    loop k in ["a" "a" "b"] {
        if k not in? table table[k]=S[0]
        table[k].count += 1
    }
    if "a" in? table printl(table["a"].count)
}''', '2\n'),
    'lock_nested_dictionary': ('''
main=()=>{
    let m=mutex(dict<string dict<string int64>>[])
    let d=@(m.lock())
    if "outer" not in? d d["outer"]=dict<string int64>[]
    if "inner" not in? d["outer"] d["outer"]["inner"]=0
    d["outer"]["inner"] += 1
    printl(d["outer"]["inner"])
}''', '1\n'),
    'lock_array_mutations': ('''
main=()=>{
    let initial:array<int64>=[]
    let m=mutex(initial)
    let xs=@(m.lock())
    xs.insert(1 0)
    printl(xs.pop() xs.length)
}''', '1 0\n'),
    'constant_division': ('''
f=(day:int64):>int64=>(day-1)//7+1
g=(a:int64 b:int64):>int64=>(a+b)//3
h=(a:int64 b:int64):>int64=>(a-b)//3
printl(f(-9223372036854775808) f(9223372036854775807) f(0) f(8))
printl(g(-9223372036854775808 -9223372036854775808) g(9223372036854775807 9223372036854775807))
printl(h(-9223372036854775808 9223372036854775807) h(9223372036854775807 -9223372036854775808))
''', '-1317624576693539401 1317624576693539401 0 2\n-6148914691236517206 6148914691236517204\n-6148914691236517205 6148914691236517205\n'),
    'increasing_divisor': ('''
f=(n:int64):>bool=>{
    let d:int64=2
    loop d*d <=? n {
        if n % d =? 0 return false
        d += 1
    }
    true
}
printl(f(17) f(25) f(100))
''', 'true false false\n'),
    'parallel_hull': ('''
f=(n:int64):>int64=>n
main=()=>{
    let xs=[loop i in [1..60] i*i+1]
    let ys=[parallel n in xs f(n)]
    if ys.length >=? 60 printl(ys.length ys[0] ys[59])
    let zs=[parallel n in [1 2 3] f(n)]
    printl(zs)
}''', '60 2 3601\n[1 2 3]\n'),
    'prefix_slice': ('''
f=(text:string):>string=>{
    if not text.startswith("=") return "absent"
    text[1..]
}
g=(text:string):>string=>{
    if text.endswith("!") return text[1..]
    "absent"
}
printl(f("=abc") f("abc") f("=é") g("é!"))
''', 'abc absent é !\n'),
    'insert_pop': ('''
f=(@xs:array<int64>):>void=>{xs.insert(2 0) xs.pop();}
main=()=>{let xs:array<int64>=[] f(@xs) printl(xs)}
''', '[]\n'),
    'refined_mutations': ('''
R:type=[xs:array<int64 length >? 0>]
main=()=>{
    let xs:array<int64 length >? 0>=[3 1 2]
    xs.insert(4 0)
    xs.sort()
    xs.reverse()
    printl(xs)
    xs.sort(key=(x)=>x)
    xs.truncate(1)
    printl(xs)
    let r=R[[2 1]]
    r.xs.insert(3 0)
    r.xs.sort()
    r.xs.reverse()
    printl(r.xs)
}
''', '[4 3 2 1]\n[1]\n[3 2 1]\n'),
    'refined_insert_selectors_once': ('''
R:type=[xs:array<int64 length >? 0>]
let calls:int64=0
index=():>int64=>{calls+=1 return 0}
main=()=>{
    let rows=[R[[1]]]
    rows[index()].xs.insert(2 0)
    printl(calls rows[0].xs)
}
''', '1 [2 1]\n'),
    'structural_equality_keeps_length': ('''
C:type=[x:int y:int]
R:type=[xs:array<C length >? 0> other:C]
f=(@r:R c:C):>void=>{
    r.xs.insert(c 0)
    if c =? r.other {return}
    r.xs.pop();
}
main=()=>{let r=R[[C[1 2]] C[0 0]] f(@r C[3 4]) printl(r.xs.length)}
''', '1\n'),
    'truncate_clamps': ('''
main=()=>{
    let xs:array<int64 length >? 0>=[1 2]
    xs.truncate(20)
    printl(xs)
}
''', '[1 2]\n'),
}


@pytest.mark.parametrize('name', PROVED)
@pytest.mark.parametrize('release', [False, True])
def test_dogfood7_proved(compiler, tmp_path, name, release):
    source, expected = PROVED[name]
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', path, '-o', binary] + (['--release'] if release else []), capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == expected


REJECTED = {
    'unbounded_dividend': 'f=(n:int):>int64=>(n-1)//7+1\nprintl(f(1))',
    'unbounded_sum': 'f=(n:int m:int):>int64=>(n+m)//7\nprintl(f(1 2))',
    'division_by_one': 'f=(n:int64):>int64=>(n-1)//1\nprintl(f(1))',
    'too_wide_difference': 'f=(n:int64 m:int64):>int64=>(n-m)//2+1\nprintl(f(1 2))',
    'zero_start': 'f=(n:int64):>bool=>{let d:int64=0 loop d*d <=? n {if n % d =? 0 return false d+=1} true}\nprintl(f(10))',
    'decreasing_divisor': 'f=(n:int64):>bool=>{let d:int64=2 loop d*d <=? n {if n % d =? 0 return false d-=1} true}\nprintl(f(10))',
    'reset_divisor': 'f=(n:int64):>bool=>{let d:int64=2 loop d*d <=? n {if n % d =? 0 return false d=0} true}\nprintl(f(10))',
    'wrapped_divisor': "f=(n:int64):>bool=>{let d:int64<overflow='wrap'>=2 loop d*d <=? n {if n % d =? 0 return false d+=1} true}\nprintl(f(10))",
    'empty_prefix': 'f=(s:string):>string=>{if not s.startswith("") return "" s[1..]}\nprintl(f(""))',
    'prefix_too_short': 'f=(s:string):>string=>{if not s.startswith("ab") return "" s[3..]}\nprintl(f("ab"))',
    'prefix_replacement': 'f=(s:string):>string=>{let t=s if not t.startswith("=") return "" t="" t[1..]}\nprintl(f("=a"))',
    'prefix_argument_write': 'zap=(@s:string):>string=>{s="" "="}\nf=(@s:string):>string=>{if not s.startswith(zap(@s)) return "" s[1..]}\nlet s="=a"\nprintl(f(@s))',
    'insert_then_clear': 'main=()=>{let xs:array<int64>=[] xs.insert(1 0) xs.clear() xs.pop();}',
    'insert_invalid_position': 'main=()=>{let xs:array<int64>=[] xs.insert(1 1) printl(xs)}',
    'truncate_empty': 'main=()=>{let xs:array<int64 length >? 0>=[1 2] xs.truncate(0) printl(xs)}',
    'insert_breaks_exact_length': 'main=()=>{let xs:array<int64 length =? 2>=[1 2] xs.insert(1 0) printl(xs)}',
    'truncate_unknown': 'f=(n:int64):>void=>{let xs:array<int64 length >? 0>=[1 2] xs.truncate(n) printl(xs)}\nf(0)',
    'parallel_unbounded': 'f=(n:int64):>int64=>n\ng=(xs:array<int>)=>[parallel n in xs f(n)]\nprintl(g([1]))',
    'parallel_mutated_hull': 'f=(n:int8):>int8=>n\nmain=()=>{let xs=[loop i in [1..3] i] xs.push(1000) printl([parallel n in xs f(n)])}',
    'lock_missing_key': 'main=()=>{let m=mutex(dict<string int64>[]) let d=@(m.lock()) printl(d["x"])}',
    'lock_clear': 'main=()=>{let m=mutex(dict<string int64>[]) let d=@(m.lock()) d["x"]=1 d.clear() printl(d["x"])}',
    'lock_helper_clear': 'clear=(@d:dict<string int64>):>void=>d.clear()\nmain=()=>{let m=mutex(dict<string int64>[]) let d=@(m.lock()) d["x"]=1 clear(@d) printl(d["x"])}',
    'lock_reacquired': 'main=()=>{let m=mutex(dict<string int64>[]) let d=@(m.lock()) d["x"]=1 let e=@(m.lock()) printl(e["x"])}',
    'lock_array_clear': 'main=()=>{let initial:array<int64>=[1] let m=mutex(initial) let xs=@(m.lock()) if xs.length >? 0 {xs.clear() printl(xs[0])}}',
    'lock_scalar_direct_write': 'main=()=>{let initial:int64=2 let m=mutex(initial) let x=@(m.lock()) if x =? 0 {return} x=0 printl(10/x)}',
    'lock_entry_direct_write': 'S:type=[count:int64]\nmain=()=>{let m=mutex(dict<string S>[]) let d=@(m.lock()) d["x"]=S[2] if d["x"].count =? 0 {return} d["x"].count=0 printl(10/d["x"].count)}',
    'lock_scalar_helper_write': 'zero=(@x:int64):>void=>{x=0}\nmain=()=>{let initial:int64=2 let m=mutex(initial) let x=@(m.lock()) if x =? 0 {return} zero(@x) printl(10/x)}',
    'lock_entry_helper_write': 'S:type=[count:int64]\nzero=(@x:int64):>void=>{x=0}\nmain=()=>{let m=mutex(dict<string S>[]) let d=@(m.lock()) d["x"]=S[2] if d["x"].count =? 0 {return} zero(@d["x"].count) printl(10/d["x"].count)}',
    'lock_replaced': 'main=()=>{let m=mutex(dict<string int64>[]) let d=@(m.lock()) d["x"]=1 d=[] printl(d["x"])}',
    'nested_custom_equality': '''
let d:dict<string int64>=[]
C:type=[id:int64]
Outer:type=[c:C]
__eq__=(a:C b:C):>bool=>{d.clear() return a.id =? b.id}
main=()=>{d["a"]=1 if Outer[C[1]] =? Outer[C[1]] printl(d["a"])}''',
    'user_hook': '''let count:int64=0
Owner=type of [value:int64 $__drop__ release=():>void=>{count+=1}]
main=()=>{let m=mutex(1) let v=@(m.lock()) printl(v)
let xs=[10 20 30] count=0 let d:dict<int64 Owner>=[] d[0]=Owner[0] d[0]=Owner[1] printl(xs[count])}''',
}


@pytest.mark.parametrize('name', REJECTED)
def test_dogfood7_still_required(compiler, tmp_path, name):
    path = tmp_path / f'{name}.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True, timeout=60)
    assert checked.returncode != 0, checked.stdout + checked.stderr
    assert 'cannot prove' in checked.stderr or 'does not fit' in checked.stderr or 'refuted' in checked.stderr or 'out of bounds' in checked.stderr or 'not in bounds' in checked.stderr or 'pop() of an empty array' in checked.stderr, checked.stderr
