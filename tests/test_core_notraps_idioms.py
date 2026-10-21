"""Everyday partial-operation idioms prove under the no-traps (require-static) policy.

Each PROVED function is one idiom; each REJECTED program keeps an invalidation
or a missing fact that must still be reported.
"""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVED = {
    # A nonzero length is at least one: `xs[0]` and `xs[end]` after an early return.
    'nonzero_length': '''peek=(xs:array<int64>):>int64=>{
    if xs.length =? 0 return 0
    return xs[0]+xs[end]+xs[xs.length-1]
}
main=():>int64=>peek([1 2])
''',
    'nonzero_scalar': '''last=(xs:array<int64> k:int64):>int64=>{
    if k <? 0 or k not=? xs.length return 0
    if k =? 0 return 0
    return xs[k-1]
}
main=():>int64=>last([1 2] 2)
''',
    # Element and field writes in a loop body keep the lengths they cannot change.
    'element_writes_keep_length': '''shift=(xs:array<int64>):>array<int64>=>{
    let out=xs
    loop i in [1..out.length) {out[i]=out[i-1]}
    loop i in [0..xs.length) {
        let bad=xs
        bad[i]=bad[i]+1
    }
    return out
}
main=():>int64=>shift([1 2 3]).length
''',
    'field_writes_keep_length': '''World:type=[ids:array<int64> score:int64]
tick=(w:World):>int64=>{
    let world=w
    loop i in [0..world.ids.length) {
        world.ids[i]=world.ids[i]+1
        world.score+=1
    }
    return world.score
}
main=():>int64=>tick(World[[1 2] 0])
''',
    # A slice proves 0 <=? lo <=? hi <=? length and has hi-lo elements.
    'slice_bounds': '''tail=(xs:array<int64>):>int64=>{
    if xs.length <? 3 return 0
    let a=xs[1..3)
    let b=xs[..2]
    let c=xs[2..]
    let d=xs[..]
    return a[1]+b[2]+c[0]+d[end]
}
main=():>int64=>tail([1 2 3])
''',
    # A loan's capacity is the length plus the reservation.
    'loan_capacity': '''grow=():>int64=>{
    let bytes:array<uint8>=[1 2 3 4]
    $lend(@bytes reserve=2) {bytes.set_length(6)}
    return bytes.length
}
main=():>int64=>grow()
''',
    # Writing elements in place (`loop @x in xs`, or a counted loop's element
    # store) keeps the length, so the hidden index and the counter stay bounded.
    'mutable_element_loop': '''Item:type=[parts:array<int64> hp:int64]
tick=(values:array<int64> items:array<Item>):>int64=>{
    let xs=values
    let ys=items
    loop @value in xs {value+=1}
    loop @item in ys {item.hp-=1}
    return xs.length+ys.length
}
main=():>int64=>tick([1 2] [])
''',
    'counted_element_writes': '''bump=(values:array<int64>):>int64=>{
    let xs=values
    let k=-1
    loop true {
        k+=1
        if k >=? xs.length break
        xs[k]+=1
    }
    return xs.length
}
main=():>int64=>bump([1 2])
''',
    # `x % n` with a positive n lies in [0, n) (the remainder has the divisor's
    # sign); `n // 2` of a positive n is smaller than n.
    'floor_remainder': '''Ring:type=[data:array<int64 length=4>=[0 0 0 0] head:int64=0 count:int64=0]
push=(@r:Ring value:int64):>void=>{
    let slot=(r.head+r.count)%4
    r.data[slot]=value
}
wrap=(xs:array<int64> i:int64):>int64=>{
    if xs.length =? 0 return 0
    return xs[i%xs.length]
}
middle=(xs:array<int64>):>int64=>{
    let n=xs.length
    if n%2 =? 1 return xs[n//2]
    return 0
}
main=():>int64=>{
    let r=Ring[]
    push(@r 3)
    return wrap([1] 5)+middle([1])
}
''',
}

REJECTED = {
    'remainder_too_wide': ('''pick=(xs:array<int64 length=3> i:int64):>int64=>xs[i%4]
main=():>int64=>pick([1 2 3] 5)
''', 'cannot prove index is in bounds: missing upper bound'),
    'remainder_unknown_divisor': ('''pick=(xs:array<int64> i:int64 k:int64):>int64=>{
    if k <? 1 return 0
    return xs[i%k]
}
main=():>int64=>pick([1] 5 1)
''', 'cannot prove index is in bounds: missing upper bound'),
    'half_of_empty': ('''middle=(xs:array<int64>):>int64=>xs[xs.length//2]
main=():>int64=>middle([1])
''', 'cannot prove index is in bounds: missing upper bound'),
    'counted_pop': ('''bump=(values:array<int64>):>int64=>{
    let xs=values
    let k=-1
    loop true {
        k+=1
        if k >=? xs.length break
        xs.pop()
        xs[k]+=1
    }
    return xs.length
}
main=():>int64=>bump([1 2])
''', 'cannot prove index is in bounds'),
    'element_of_element': ('''Item:type=[parts:array<int64> hp:int64]
tick=(items:array<Item>):>int64=>{
    let ys=items
    loop @item in ys {item.parts[0]+=1}
    return 0
}
main=():>int64=>tick([])
''', 'cannot prove index is in bounds: missing upper bound'),
    'slice_past_end': ('''main=():>int64=>{
    let xs:array<int64>=[1 2]
    return xs[1..3).length
}
''', 'slice is not in bounds'),
    'slice_reversed': ('''cut=(xs:array<int64> k:int64):>int64=>{
    if k >? xs.length return 0
    return xs[k..).length
}
main=():>int64=>cut([1] 1)
''', 'cannot prove slice is in bounds: missing lower bound'),
    'slice_after_shrink': ('''cut=(xs:array<int64>):>int64=>{
    let ys=xs
    if ys.length <? 2 return 0
    ys.pop()
    return ys[..1].length
}
main=():>int64=>cut([1 2])
''', 'cannot prove slice is in bounds: missing upper bound'),
    'guard_without_exit': ('''peek=(xs:array<int64>):>int64=>{
    if xs.length =? 0 {printl"empty"}
    return xs[0]
}
main=():>int64=>peek([1])
''', 'cannot prove index is in bounds: missing upper bound'),
    'pop_after_guard': ('''peek=(xs:array<int64>):>int64=>{
    let ys=xs
    if ys.length =? 0 return 0
    ys.pop()
    return ys[0]
}
main=():>int64=>peek([1])
''', 'cannot prove index is in bounds: missing upper bound'),
    'resize_in_loop': ('''drain=(xs:array<int64>):>int64=>{
    let ys=xs
    let t=0
    loop i in [0..ys.length) {
        ys.pop()
        t+=ys[i]
    }
    return t
}
main=():>int64=>drain([1])
''', 'cannot prove index is in bounds: missing upper bound'),
    'field_resize_in_loop': ('''World:type=[ids:array<int64> score:int64]
tick=(w:World):>int64=>{
    let world=w
    loop i in [0..world.ids.length) {
        world.ids.clear()
        world.ids[i]=1
    }
    return 0
}
main=():>int64=>tick(World[[1 2] 0])
''', 'index is not in bounds'),
    'record_replaced_in_loop': ('''World:type=[ids:array<int64> score:int64]
tick=(w:World):>int64=>{
    let world=w
    loop i in [0..world.ids.length) {
        world=World[[] 0]
        world.ids[i]=1
    }
    return 0
}
main=():>int64=>tick(World[[1 2] 0])
''', 'index is not in bounds'),
}


def check(compiler, tmp_path, name, source):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=30,
                          env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'})


@pytest.mark.parametrize('name', PROVED)
def test_notraps_idiom_proved(compiler, tmp_path, name):
    result = check(compiler, tmp_path, name, PROVED[name])
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('name', REJECTED)
def test_notraps_idiom_rejected(compiler, tmp_path, name):
    source, message = REJECTED[name]
    result = check(compiler, tmp_path, name, source)
    assert result.returncode != 0
    assert message in result.stdout + result.stderr, result.stdout + result.stderr
