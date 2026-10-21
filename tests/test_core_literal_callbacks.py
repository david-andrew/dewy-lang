"""Literal and forwarded environments retain value semantics at escape edges."""
import pytest

from tests.support import compiler, run_value_batch


CASES = {
    'literal-and-forwarded-allocation': '''Callback:type=():>int64
invoke=(callback:Callback before:int64):>int64=>{
 if alloc_count() not=?before return 1
 return callback()
}
forward=(callback:Callback before:int64):>int64=>invoke(@callback before)
main=()=>{
 let n:int64=21
 let before=alloc_count()
 return invoke(()=>n before)+forward(()=>n before)
}''',
    'named-forwarded-allocation': '''Callback:type=():>int64
invoke=(callback:Callback before:int64):>int64=>{
 if alloc_count() not=?before return 1
 return callback()
}
forward=(callback:Callback before:int64):>int64=>invoke(@callback before)
main=()=>{
 let n:int64=42
 let before=alloc_count()
 let callback=()=>n
 return forward(@callback before)
}''',
    'managed-literal-cleanup': '''Callback:type=():>int64
invoke=(callback:Callback):>int64=>callback()
forward=(callback:Callback):>int64=>invoke(@callback)
exercise=(n:int64):>int64=>{
 let values:array<int64>=[n]
 return forward(()=>values[0])
}
main=()=>{
 let before=alloc_count()
 loop i in [0..20) {
  if exercise(42) not=?42 return 1
  if alloc_count() not=?before return 2
 }
 return 42
}''',
    'forwarded-escape': '''Callback:type=():>int64
let saved:array<Callback>=[]
retain=(callback:Callback)=>{saved.push(@callback)}
forward=(callback:Callback)=>retain(@callback)
make=(n:int64)=>forward(()=>n)
main=()=>{make(42) return saved[0]()}''',
    'returned-literal': '''Callback:type=():>int64
identity=(callback:Callback):>Callback=>@callback
forward=(callback:Callback):>Callback=>identity(@callback)
make=(n:int64):>Callback=>forward(()=>n)
main=()=>{let callback=make(42) return callback()}''',
    'forwarded-mutable-snapshot': '''Callback:type=():>int64
invoke=(callback:Callback):>int64=>callback()+callback()
forward=(callback:Callback):>int64=>invoke(@callback)+callback()
main=()=>{
 let n:int64=0
 let callback=()=>{n+=1 return n}
 let a=forward(@callback)
 let b=forward(()=>{n+=1 return n})
 return if a=?4 and b=?4 and callback()=?1 and n=?0 42 else 1
}''',
    'reordered-keyword-arguments': '''Callback:type=():>int64
invoke=(callback:Callback before:int64):>int64=>{
 if alloc_count() not=?before return 1
 return callback()
}
main=()=>{
 let n:int64=42
 let before=alloc_count()
 return invoke(before=before callback=()=>n)
}''',
    'library-literals': '''main=()=>{
 let n:int64=7
 let xs:array<int64>=[1 2 3]
 let before=alloc_count()
 if not xs.any(x=>x=?n-5) return 1
 if alloc_count() not=?before return 2
 let ys=xs.map(x=>x+n)
 let zs=ys.filter(x=>x>?n+1)
 xs.each(x=>{$runtime_assert x<?n})
 xs.sort(key=x=>n-x)
 if xs[0] not=?3 or zs.length not=?2 return 3
 return ys.reduce(15 (a x)=>a+x)
}''',
    'recursive-retaining-cycle': '''Callback:type=():>int64
let saved:array<Callback>=[]
forward=(callback:Callback n:int64)=>{
 if n=?0 {saved.push(@callback) return}
 forward(@callback n-1)
}
make=(n:int64)=>forward(()=>n 3)
main=()=>{make(42) return saved[0]()}''',
}


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_literal_callback_boundaries(compiler, tmp_path, release, target):
    for name, (code, diagnostic) in run_value_batch(
            compiler, tmp_path, CASES, release, target).items():
        assert code == '42', f'{name}: {diagnostic or code}'
