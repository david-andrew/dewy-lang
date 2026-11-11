"""A higher-order call keeps facts about `@` places when its callbacks write nothing."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'sorted_key': ('''f=(@xs:array<int64>)=>{
    let n=xs.length
    let ys=xs.sorted(key=(v:int64)=>-v)
    if n >? 0 printl(xs[n-1] + ys[0])
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs)}''', '5\n'),
    'sorted_named_key': ('''k=(v:int64):>int64=>v
f=(@xs:array<int64>)=>{
    let n=xs.length
    let ys=xs.sorted(key=@k)
    if n >? 0 printl(xs[n-1] + ys[0])
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs)}''', '3\n'),
    'map_other': ('''f=(@xs:array<int64> @ys:array<int64>)=>{
    let n=xs.length
    let zs=ys.map((v:int64)=>v*2)
    if n >? 0 printl(xs[n-1] + zs.length)
}
main=()=>{let xs:array<int64>=[3 1 2] let ys:array<int64>=[4] f(@xs @ys)}''', '3\n'),
    'filter_other': ('''f=(@xs:array<int64> @ys:array<int64>)=>{
    let n=xs.length
    let zs=ys.filter((v:int64)=>v >? 1)
    if n >? 0 printl(xs[n-1] + zs.length)
}
main=()=>{let xs:array<int64>=[3 1 2] let ys:array<int64>=[4] f(@xs @ys)}''', '3\n'),
    'min_by_other': ('''f=(@xs:array<int64> @ys:array<int64>)=>{
    let n=xs.length
    if ys.length >? 0 printl(ys.min_by((v:int64)=>-v))
    if n >? 0 printl(xs[n-1])
}
main=()=>{let xs:array<int64>=[3 1 2] let ys:array<int64>=[4 5] f(@xs @ys)}''', '5\n2\n'),
    # (a program's own higher-order functions, forwarding the callback and recursing)
    'own_hof': ('''twice=(k:(v:int64:>int64) x:int64):>int64=>k(k(x))
walk=(k:(v:int64:>int64) n:int64):>int64=>if n <=? 0 {k(0)} else {max(k(n) walk(@k n-1))}
f=(@xs:array<int64>)=>{
    let n=xs.length
    let r=max(twice((v:int64)=>v 1) walk((v:int64)=>v 3))
    if n >? 0 printl(xs[n-1] + r)
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs)}''', '5\n'),
    # (a callback reading only its own copies of captured values)
    'copy_capture_key': ('''f=(@xs:array<int64> rank:array<int64>)=>{
    let n=xs.length
    if rank.length =? n {
        let order=[loop i in [0..n) i].sorted(key=(i) => rank[i])
        if n >? 0 printl(xs[n-1] + order[0])
    }
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs [5 6 7])}''', '2\n'),
    'copy_capture_self': ('''f=(@xs:array<int64>)=>{
    let n=xs.length
    let order=[loop i in [0..n) i].sorted(key=(i) => xs[i])
    if n >? 0 printl(xs[n-1] + order[0])
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs)}''', '3\n'),
    'copy_capture_scalar': ('''f=(@xs:array<int64> ws:array<int64>)=>{
    let n=xs.length
    let k:int64=3
    let zs=ws.map((v:int64)=>v * k)
    if n >? 0 printl(xs[n-1] + zs.length)
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs [1 2])}''', '4\n'),
}
REJECTED = {
    # (the callback writes a global the `@` parameter may be)
    'key_writes_global': '''let G:array<int64>=[3 1 2]
f=(@xs:array<int64>)=>{
    let n=xs.length
    let ys=xs.sorted(key=(v:int64)=>{G.clear(); v})
    if n >? 0 printl(xs[n-1])
}
main=()=>f(@G)''',
    'named_key_writes_global': '''let G:array<int64>=[3 1 2]
k=(v:int64):>int64=>{G.clear(); v}
f=(@xs:array<int64>)=>{
    let n=xs.length
    let ys=xs.sorted(key=@k)
    if n >? 0 printl(xs[n-1])
}
main=()=>f(@G)''',
    'map_writes_global': '''let G:array<int64>=[3 1 2]
f=(@xs:array<int64> ys:array<int64>)=>{
    let n=xs.length
    let zs=ys.map((v:int64)=>{G.clear(); v})
    if n >? 0 printl(xs[n-1])
}
main=()=>f(@G [1 2])''',
    # (the callback captures the array and changes it)
    'capture_push': '''main=()=>{
    let xs:array<int64>=[3 1 2]
    let n=xs.length
    let ys=xs.sorted(key=(v:int64 $capture @xs)=>{xs.push(v); v})
    if n >? 0 printl(xs[n-1])
}''',
    'capture_clear_filter': '''main=()=>{
    let xs:array<int64>=[3 1 2]
    let ws:array<int64>=[1 2]
    let n=xs.length
    let zs=ws.filter((v:int64 $capture @xs)=>{xs.clear(); v >? 0})
    if n >? 0 printl(xs[n-1])
}''',
    # (a copy-capturing callback that writes a global, or changes a capture)
    'copy_capture_writes_global': '''let G:array<int64>=[3 1 2]
f=(@xs:array<int64>)=>{
    let n=xs.length
    let k:int64=2
    let order=[loop i in [0..n) i].sorted(key=(i) => {G.clear(); i * k})
    if n >? 0 printl(xs[n-1])
}
main=()=>f(@G)''',
    'value_capture_changed': '''f=(@xs:array<int64> ws:array<int64>)=>{
    let n=xs.length
    let c:int64=0
    let zs=ws.map((v:int64 $capture c)=>{c += 1; v + c})
    if n >? 0 printl(xs[n-1])
}''',
    'place_capture_counter': '''f=(@xs:array<int64> ws:array<int64>)=>{
    let n=xs.length
    let c:int64=0
    let zs=ws.map((v:int64 $capture @c)=>{c += 1; v})
    if n >? 0 printl(xs[n-1] + c)
}''',
    # (a callback passed in, or one calling a function passed in, is unknown)
    'key_parameter': '''f=(@xs:array<int64> k:(v:int64:>int64))=>{
    let n=xs.length
    let ys=xs.sorted(key=@k)
    if n >? 0 printl(xs[n-1])
}''',
    'map_parameter': '''f=(@xs:array<int64> ys:array<int64> k:(v:int64:>int64))=>{
    let n=xs.length
    let zs=ys.map(@k)
    if n >? 0 printl(xs[n-1])
}''',
    'key_calls_parameter': '''f=(@xs:array<int64> h:(v:int64:>int64))=>{
    let n=xs.length
    let ys=xs.sorted(key=(v:int64)=>h(v))
    if n >? 0 printl(xs[n-1])
}''',
    # (the callback calls a foreign function)
    'key_calls_extern': '''getpid=():>int32 => $extern
f=(@xs:array<int64>)=>{
    let n=xs.length
    let ys=xs.sorted(key=(v:int64)=>{$unsafe v + int64(getpid())})
    if n >? 0 printl(xs[n-1])
}
main=()=>{let xs:array<int64>=[3 1 2] f(@xs)}''',
    # (a higher-order function calling a writer of its own, or passing its
    # callback a place to change)
    'own_hof_inner_writer': '''let G:array<int64>=[1 2 3]
apply=(g:(v:int64:>int64) x:int64):>int64=>g(x)
hof=(k:(v:int64:>int64) x:int64):>int64=>max(apply((v:int64)=>{G.clear(); v} x) apply(@k x))
f=(@xs:array<int64>)=>{
    let n=xs.length
    let r=hof((v:int64)=>v 1)
    if n >? 0 printl(xs[n-1])
}
main=()=>f(@G)''',
    'own_hof_place_argument': '''hof=(@ys:array<int64> k:(@a:array<int64>:>void))=>k(@ys)
f=(@xs:array<int64> @ws:array<int64>)=>{
    let n=xs.length
    hof(@ws (@a:array<int64>)=>a.clear())
    if n >? 0 printl(xs[n-1])
}''',
}


@pytest.mark.parametrize('name', PROVED)
def test_callback_row_facts_prove(compiler, tmp_path, name):
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
def test_callback_row_facts_reject(compiler, tmp_path, name):
    path = tmp_path / 'stale.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'index is in bounds' in checked.stdout + checked.stderr, checked.stdout + checked.stderr
