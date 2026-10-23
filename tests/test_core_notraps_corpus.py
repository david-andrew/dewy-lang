"""Facts the no-traps corpus leans on: shared fill counts, count-parameter result
lengths, sibling field contracts on read, and constant-offset contract bounds."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVED = {
    # Two fills of one count have one length, whatever the count's sign.
    'fills_of_one_count': '''pairs=(n:int64):>int64=>{
    let xs=fill(0 n)
    let ys=fill(false n)
    let t=0
    loop i in [0..xs.length) {if ys[i] {t+=xs[i]}}
    loop i in [0..n) {t+=xs[i]}
    return t
}
main=():>void=>exit(pairs(3))
''',
    # A local function's result length follows its count parameter.
    'count_parameter_result': '''make=(n:int64):>array<int64>=>{
    let d=fill(int64(7) n)
    return d
}
squares=(n:int64):>array<int64>=>[loop i in [0..n) i*i]
main=():>void=>{
    let r=make(5)
    let q=squares(4)
    exit(r[4]+q[3]-16)
}
''',
    # A field's contract naming a sibling holds for every stored record.
    'sibling_field_contract': '''Soa:type=[ids:array<int64> x:array<int64 length =? ids.length> used:int64<0 <=? used and used <=? ids.length>]
total=(w:Soa):>int64=>{
    let t=0
    loop i in [0..w.ids.length) {t+=w.x[i]}
    loop i in [0..w.used) {t+=w.ids[i]}
    return t
}
main=():>void=>exit(total(Soa[[1 2] [3 4] 1]))
''',
    # Contract bounds take a constant offset; callers prove it like any bound.
    'offset_contract': '''load16=(b:array<uint8> at:int64<0 <=? at and at+2 <=? b.length>):>int64=>(b[at] as int64)+(b[at+1] as int64)*256
scan=(src:array<uint8> start:int64<(>=? 0)> stop:int64<(<=? src.length)>):>int64=>{
    let i=start
    let n=0
    loop i <? stop {
        if src[i] =? 35 and i+1 <? stop and src[i+1] =? 35 {n+=1}
        i+=1
    }
    return n
}
main=():>void=>{
    let xs:array<uint8>=[1 2 35 35 5]
    exit(load16(xs 3)-140+scan(xs 0 xs.length)+scan(xs 1 3))
}
''',
    # A counter its loop tests at an offset relates to the bound through the
    # body's own values (`i+2 <? n`, then `i+=3`): every read below n.
    'offset_guarded_counter': '''triples=(b:array<uint8>):>int64=>{
    let n=b.length
    let t=0
    let i=0
    loop i + 2 <? n {
        t+=(b[i] as int64)+(b[i+1] as int64)+(b[i+2] as int64)
        i+=3
    }
    return t
}
main=():>void=>exit(triples([1 2 3 4]))
''',
    # A run of constant offsets after one guard keeps every offset's rows.
    'offset_run': '''g=(b:array<uint8> p:int64):>uint8=>{
    if p <? 0 or p >? b.length-16 return 0
    return b[p+1] or b[p+2] or b[p+3] or b[p+4] or b[p+5] or b[p+6]
}
main=():>void=>exit(g([1 2 3] 0) as int64)
''',
    # A vector constructor reads its operands and writes nothing.
    'vector_constructor': '''f=():>int64=>{
    let b=[1 2]
    let v=vec3(0.0 0.0 1.0)
    b[1]=3
    return b[0]
}
main=():>void=>exit(f())
''',
    # extend grows by its operand's length, truncate never grows, and neither
    # forgets what it does not write.
    'extend_truncate': '''f=(data:array<uint8> at:int64):>int64=>{
    if at <? 0 or at >? data.length return 0
    let out:array<uint8>=[]
    out.extend(data[at..])
    let k=at
    out.truncate(2)
    let ys:array<int64>=[1 2 3]
    ys.extend([4])
    return out.length+data[k..].length+ys[3]
}
main=():>void=>exit(f([1 2] 1))
''',
    # A range loop's argmax holds its entry value or an earlier index.
    'argmax_index': '''nearest=(xs:array<int64 length >? 0> k:int64):>int64<r => 0 <=? r and r <? xs.length>=>{
    let best=0
    loop i in [1..xs.length) {if xs[i]-k <? xs[best]-k {best=i}}
    return best
}
argmin=(xs:array<int64>):>int64=>{
    let u=-1
    loop i in [0..xs.length) {if u <? 0 or xs[i] <? xs[u] {u=i}}
    if u <? 0 return 0
    return xs[u]
}
main=():>void=>exit(nearest([3 1 2] 0)+argmin([3 1 2]))
''',
    # Reviewed prelude contracts: parallel results have one value per input.
    'parallel_lengths': '''main=():>void=>{
    let input=[loop i in [0..16) i]
    let output=parallel_map(input (n)=>n+1)
    let nested=parallel_range(8 (i:int64)=>i*2)
    let t=nested[7]
    loop i in [0..input.length) {t+=output[i]}
    exit(t-150)
}
''',
    # A push makes the length exactly one more: the old length indexes it.
    'append_index': '''append=(@xs:array<int64> value:int64):>addr<i => i <? xs.length>=>{
    let i=xs.length
    xs.push(value)
    return i
}
main=():>void=>{
    let xs:array<int64>=[]
    let i=append(@xs 3)
    exit(xs[i])
}
''',
}

REJECTED = {
    # A fill of a different count says nothing about another's length.
    'fills_of_two_counts': ('''pairs=(n:int64 m:int64):>int64=>{
    let xs=fill(0 n)
    let ys=fill(0 m)
    let t=0
    loop i in [0..xs.length) {t+=ys[i]}
    return t
}
main=():>void=>exit(pairs(3 3))
''', 'cannot prove index is in bounds: missing upper bound'),
    # A counter that steps past its offset guard's slack is not kept in bounds.
    'offset_guard_too_loose': ('''pairs=(b:array<uint8>):>int64=>{
    let t=0
    let i=0
    loop i + 1 <? b.length {
        t+=b[i+2] as int64
        i+=1
    }
    return t
}
main=():>void=>exit(pairs([1 2 3]))
''', 'cannot prove index is in bounds'),
    # Set to something other than the loop's value, the argmax proves nothing.
    'argmax_other_value': ('''pick=(xs:array<int64>):>int64=>{
    if xs.length =? 0 return 0
    let best=0
    loop i in [1..xs.length) {if xs[i] <? 0 {best=i+1}}
    return xs[best]
}
main=():>void=>exit(pick([3 1 2]))
''', 'cannot prove index is in bounds'),
    'offset_contract_too_short': ('''load16=(b:array<uint8> at:int64<0 <=? at and at+2 <=? b.length>):>int64=>(b[at] as int64)+(b[at+2] as int64)
main=():>void=>exit(load16([1 2 3] 0))
''', 'cannot prove index is in bounds: missing upper bound'),
    'offset_argument_refuted': ('''load16=(b:array<uint8> at:int64<0 <=? at and at+2 <=? b.length>):>int64=>b[at] as int64
main=():>void=>exit(load16([1 2 3] 2))
''', 'refinement refuted'),
}


def check(compiler, tmp_path, name, source):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=30,
                          env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'})


@pytest.mark.parametrize('name', PROVED)
def test_corpus_fact_proved(compiler, tmp_path, name):
    result = check(compiler, tmp_path, name, PROVED[name])
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('name', REJECTED)
def test_corpus_fact_rejected(compiler, tmp_path, name):
    source, message = REJECTED[name]
    result = check(compiler, tmp_path, name, source)
    assert result.returncode != 0
    assert message in result.stdout + result.stderr, result.stdout + result.stderr


# An unproven offset bound is an exact runtime check under the default policy,
# including near the integer limits, where a wrapped `x-2` would pass.
RUNTIME = {
    'upper': ("""load16=(b:array<uint8> at:int64<0 <=? at and at+2 <=? b.length>):>int64=>b[at] as int64
main=(args:array<string>):>void=>{
    let xs:array<uint8>=[1 2 3]
    let k=args.length
    printl(load16(xs k))
    printl(load16(xs k+1))
}
""", 'observed: the value was 2 and the bound was 1'),
    'wrapped': ("""below=(x:int64 limit:int64<(<? x-2)>):>int64=>limit
main=(args:array<string>):>void=>{
    let k=args.length
    printl(below(k+5 k))
    printl(below(int64.min+k int64.min+k-1))
}
""", 'refinement failed'),
}


@pytest.mark.parametrize('name', RUNTIME)
def test_offset_contract_runtime_check(compiler, tmp_path, name):
    source, message = RUNTIME[name]
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    result = subprocess.run([compiler, 'run', path], text=True, capture_output=True, timeout=60, cwd=tmp_path)
    assert result.returncode == 101, result.stdout + result.stderr
    assert result.stdout.splitlines() == ['2' if name == 'upper' else '1'], result.stdout
    assert message in result.stderr, result.stderr
