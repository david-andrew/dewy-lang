"""Facts behind the no-traps default: integer min/max, sums of two symbolic
operands related through terms already evaluated, a fork closure's entry from
its creator, one-way loop counters, and a pool's direct update as the
library's own obligation."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVED = {
    # min is below each operand; its interval is theirs combined.
    'min_bounds': '''f=(xs:array<int64> n:int64):>int64=>{
    let out:array<int64>=[loop i in [0..32) i]
    let t=0
    loop j in [0..min(32 n)) {t+=out[j]}
    loop j in [0..min(n xs.length)) {t+=xs[j]}
    return t
}
main=():>void=>exit(f([1 2 3] 2)-2)
''',
    # max is above each operand.
    'max_bounds': '''f=(xs:array<int64> k:int64):>int64=>{
    let t=0
    loop j in [0..xs.length) {if max(j k) <? xs.length {t+=xs[j]}}
    let i=max(0 k)
    if i <? xs.length {t+=xs[i]}
    return t
}
main=():>void=>exit(f([1 2 3] 1)-8)
''',
    # first+j against a guarded first+n: the shared operand's partner rows.
    'sum_shared_operand': '''g=(a:array<int64> first:int64 n:int64):>int64=>{
    if not (0 <=? first and first <? a.length and 0 <=? n and n <=? a.length and first+n <=? a.length) return 0
    let t=0
    loop j in [0..n) {t+=a[first+j]}
    loop j in [1..n-1) {let p=first+j t+=a[p-1]+a[p+1]}
    return t
}
main=():>void=>exit(g([1 2 3 4] 1 3)-12)
''',
    # col+j with j below n-col: the difference term's rows bound the sum.
    'sum_complement': '''f=(xs:array<int64> n:int64 col:int64):>int64=>{
    if col <? 0 or col >? n or n >? xs.length return 0
    let t=0
    loop j in [0..min(32 n-col)) {t+=xs[col+j]}
    return t
}
main=():>void=>exit(f([1 2 3] 3 1)-5)
''',
    # A fork closure starts from what its creator knew of its snapshot
    # captures and of the lengths of the arrays it borrows by partition.
    'fork_slices': '''fill=(@xs:array<int64> @ys:array<int64> v:int64):>void=>{
    loop i in [0..xs.length) {xs[i]=v}
    loop i in [0..ys.length) {ys[i]=v}
}
sort=(@a:array<int64> @tmp:array<int64>):>void=>{
    let n=a.length
    if n <=? 1 return
    if tmp.length not=? n return
    let mid=n//2
    let _joined=parallel_range(2 ($capture @a $capture @tmp i:int64):>int64=>{
        if i =? 0 {fill(@a[..mid) @tmp[..mid) 1)}
        else {fill(@a[mid..] @tmp[mid..] 2)}
        return 0
    })
}
main=():>void=>{
    let a:array<int64>=[0 0 0 0]
    let t:array<int64>=[0 0 0 0]
    sort(@a @t)
    exit(0)
}
''',
    # `% 128` is a mask: below 128 whatever the dividend.
    'power_of_two_modulo': '''k=(rows:array<int64> count:int64):>int64=>{
    let total:int64=0
    if rows.length <? 128 return 0
    loop i in [0..count) {total+=rows[i%128]}
    let b:uint8=((count+1)%128) as uint8
    return total+(b as int64)
}
main=():>void=>exit(k([1] 3))
''',
    # A counter that only moves down stays at most its entry value.
    'decreasing_counter': '''reverse=(@values:array<int64>):>void=>{
    let low:int64=0
    let high=values.length
    loop low+1 <? high {
        high-=1
        let kept=values[low]
        values[low]=values[high]
        values[high]=kept
        low+=1
    }
}
main=():>void=>{
    let v:array<int64>=[1 2 3]
    reverse(@v)
    exit(0)
}
''',
    # `pool[h].field -= x` indexes the pool's items at its own checked answer.
    'pool_direct_update': '''Enemy:type=[name:string health:int64=100]
main=():>void=>{
    let enemies:Pool<Enemy>=[]
    let scout=enemies.add(Enemy[name="scout"])
    if enemies.has(scout) {enemies[scout].health-=10}
    exit(0)
}
''',
}

REJECTED = {
    # max is not below its operands.
    'max_not_below': ('''f=(xs:array<int64> n:int64):>int64=>{
    let t=0
    loop j in [0..max(n xs.length)) {t+=xs[j]}
    return t
}
main=():>void=>exit(f([1] 1))
''', 'cannot prove index is in bounds'),
    # A loose guard on the shared operand's partner proves nothing.
    'sum_loose_partner': ('''g=(a:array<int64> first:int64 n:int64):>int64=>{
    if not (0 <=? first and first <? a.length and 0 <=? n and n <=? a.length and first+n <=? a.length) return 0
    let t=0
    loop j in [0..n+1) {t+=a[first+j]}
    return t
}
main=():>void=>exit(g([1 2] 0 1))
''', 'cannot prove index is in bounds'),
    # Its entry value itself is past the end.
    'decreasing_from_length': ('''f=(xs:array<int64>):>int64=>{
    let t=0
    let high=xs.length
    loop high >? 0 {
        t+=xs[high]
        high-=1
    }
    return t
}
main=():>void=>exit(f([1]))
''', 'cannot prove index is in bounds'),
    # A closure that is not a fork's runs later: its creator's facts say nothing.
    'stored_closure': ('''main=():>void=>{
    let xs:array<int64>=[1 2 3 4]
    let mid=xs.length//2
    let later=(i:int64):>int64=>xs[..mid).length+i
    exit(later(0)-2)
}
''', 'cannot prove slice is in bounds'),
}


def check(compiler, tmp_path, name, source):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=30,
                          env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'})


# The pool index fact holds, but __pool_index still panics in the library
# until pool handles carry a liveness proof (the panics effect reports it).
PANICS_PENDING = {'pool_direct_update'}


@pytest.mark.parametrize('name', [pytest.param(n, marks=pytest.mark.xfail(reason='pool index panics until handles carry liveness', strict=True)) if n in PANICS_PENDING else n for n in PROVED])
def test_gap_fact_proved(compiler, tmp_path, name):
    result = check(compiler, tmp_path, name, PROVED[name])
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('name', REJECTED)
def test_gap_fact_rejected(compiler, tmp_path, name):
    source, message = REJECTED[name]
    result = check(compiler, tmp_path, name, source)
    assert result.returncode != 0
    assert message in result.stdout + result.stderr
