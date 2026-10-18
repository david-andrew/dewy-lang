"""Expected user behavior for the experimental source-level core."""
import base64
import ctypes
import json
import math
import os
import platform
import random
import re
import shutil
import struct
import subprocess
import zlib
from decimal import Decimal, localcontext
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.python_misc.core_glsl_driver import DriverUnavailable, ShaderDriver
from tools.sloppy_core.benchmark_apps import CHECKSUMS_1000, prepare_source
from tools.sloppy_core.benchmark_types import record_source

# A small cross-section of user behavior, reusing the full gate's batched cases.
QUICK_CASES = {
    'constant-local-once', 'numeric-sum-literal-exact', 'numeric-matrix-slices',
    'array-comparison-word-boundaries', 'sequence-value-protocol-nesting',
    'closure-copy-private', 'closure-explicit-shared', 'closure-copy-cleanup',
    'closure-capture-parameters',
    'sequence-closures', 'sequence-slice-loop-snapshots', 'sequence-mutable-snapshot-in-body',
    'dictionary-presence-argument-order', 'dictionary-optional-managed-payload',
    'dictionary-value-equality', 'set-copy-and-removal', 'numeric-bounds',
    'rational-division-notation', 'bigint-mixed-and-copies',
    'generic-instance-identity', 'generic-instance-recursion', 'generic-return-closure',
    'named-managed-order', 'argument-borrow-callback-write', 'record-spread-order',
    'unpack-dictionary-nested', 'loop-else-conditions', 'json-typed-nested',
    'optional-managed-copy', 'grapheme-loop', 'optimizer-nested-exits',
    'fixed-array-values', 'fixed-array-dynamic-conversion',
}
QUICK_ERRORS = {'generic-value-conflicting-type', 'coalesce-nonoptional', 'array-comparison-overflow'}
VALUE_BATCH_SIZE = 64


def quick_parameters(names, selected):
    names = list(names)
    missing = selected.difference(names)
    if missing:
        raise ValueError(f'Quick-suite cases no longer exist: {sorted(missing)}')
    return [pytest.param(name, marks=pytest.mark.core_quick if name in selected else ()) for name in names]


CASES = {
    'closure-argument-container-values': '''Counter:type=():>int64
Box:type=[next:Counter]
make=()=>{let n=0 return ()=>{n+=1; n}}
from_array=(xs:array<Counter>)=>xs[0]()+xs[0]()
from_box=(box:Box)=>box.next()+box.next()
main=()=>{let xs=[make()] let box=Box[make()]
if from_array(xs) not=?3 or from_array(xs) not=?3 or xs[0]() not=?1 return 1
return if from_box(box)=?3 and from_box(box)=?3 and box.next()=?1 42 else 2}''',
    'closure-argument-evaluation-order': '''Counter:type=():>int64
make=()=>{let n=0 return ()=>{n+=1; n}}
read=(f:Counter ignored:int64)=>f()
main=()=>{let f=make()
if read(f f()) not=?1 return 1
if read(ignored=f() f=f) not=?3 return 2
return if f()=?3 42 else 3}''',
    'closure-argument-indirect-forwarding': '''Counter:type=():>int64
make=()=>{let n=0 return ()=>{n+=1; n}}
twice=(f:Counter)=>f()+f()
forward=(f:Counter)=>{let run=twice return run(f)+f()}
main=()=>{let f=make()
return if forward(f)=?4 and forward(f)=?4 and f()=?1 42 else 1}''',
    'closure-capture-constants': '''main=()=>{const n=20 const word="hello" const xs=[22]
let a=($capture n $capture word $capture xs)=>if word=?"hello" n+xs[0] else 1
let b=($capture @n $capture @word $capture @xs)=>if word=?"hello" n+xs[0] else 1
return if a()=?42 and b()=?42 42 else 1}''',
    'closure-capture-parameters': '''Callback:type=(step:int64 extra:int64):>int64
apply=(f:Callback)=>f(2 3)
main=()=>{let count=0 let total=0 let initial=10
let next=($capture @count step:int64 $capture initial extra:int64 $capture @total):>int64=>{
count+=1 total+=step+extra initial+=1; initial}
let other=next initial=100
if next(2 3) not=?11 or other(4 5) not=?11 or next(0 1) not=?12 return 1
if apply(next) not=?13 or next(0 0) not=?13 return 2
return if count=?5 and total=?20 and initial=?100 42 else 3}''',
    'closure-capture-private-explicit': '''make=(value:int64)=>($capture value)=>{value+=1; value}
main=()=>{let a=make(10) let b=a
if a() not=?11 or a() not=?12 or b() not=?11 return 1
let xs=[20 22] let read=($capture xs)=>{xs[0]+=1; xs[0]}
xs[0]=100 let copy=read
return if read()=?21 and copy()=?21 and read()=?22 and xs[0]=?100 42 else 2}''',
    'closure-capture-mutable-argument': '''main=()=>{let calls=0 let count=40
let advance=(@value:int64 $capture @calls)=>{calls+=1 value+=1}
advance(@count) advance(@count)
return if count=?42 and calls=?2 42 else 1}''',
    'closure-copy-cleanup': '''make=()=>{let n=0 let values=[1 2 3]
return ()=>{n+=1 values.push(n); n+values.length}}
work=()=>{let a=make() let b=a let xs=[a b] let ys=xs
let record=[run=a rows=[xs]] let other=record
let shared=0 let c=($capture @shared)=>{shared+=1; shared} let d=c
loop i in [0..10) {xs[0]() ys[1]() other.run() c() d()}
}
main=()=>{let before=alloc_count() loop i in [0..20) work()
return if alloc_count()=?before 42 else 1}''',
    'closure-recursive-container-copies': '''Counter:type=():>int64
A:type=[children:array<B> next:Counter]
B:type=[parents:array<A>]
make=()=>{let n=0 return ()=>{n+=1; n}}
main=()=>{let a=A[[] make()] let keep=a let bs=[B[[a]]] let other=bs
if bs[0].parents[0].next() not=?1 or other[0].parents[0].next() not=?1 return 1
return if a.next()=?1 and keep.next()=?1 42 else 2}''',
    'closure-loop-capture-value': '''main=()=>{let values=[20 22] let total=0
loop value in values {let later=()=>{value+=1; value} total+=later()}
return if total=?44 and values[0]=?20 and values[1]=?22 42 else 1}''',
    'closure-mutable-loop-snapshot': '''main=()=>{let xs=[20 22] let readers:array<():>int64>=[]
loop @x in xs {readers.push(()=>{x+=1; x}) x+=10}
return if readers[0]()=?21 and readers[1]()=?23 and xs=?[30 32] 42 else 1}''',
    'closure-narrowed-shared': '''main=()=>{let n:int64|string=40
if n is? int64 {let next=($capture @n)=>{n+=1; n} next() return next()}
return 1}''',
    'closure-copy-private': '''make=()=>{let count=0 return ()=>{count+=1; count}}
main=()=>{let a=make() let b=a
if a() not=?1 or b() not=?1 or a() not=?2 return 1
let c=a
return if c()=?3 and a()=?3 and b()=?2 42 else 2}''',
    'closure-capture-snapshots': '''main=()=>{let n=10 let xs=[20]
let a=()=>{n+=1 xs[0]+=1 return n+xs[0]}
let b=()=>n+xs[0]
n=100 xs[0]=200
if a() not=?32 or a() not=?34 or b() not=?30 return 1
return if n=?100 and xs[0]=?200 42 else 2}''',
    'closure-explicit-shared': '''make=()=>{let n=0 return ($capture @n)=>{n+=1; n}}
main=()=>{let a=make() let b=a
if a() not=?1 or b() not=?2 return 1
let n=10 let read=($capture @n)=>n let inc=($capture @n)=>{n+=1}
inc() n+=1
return if read()=?12 and a()=?3 42 else 2}''',
    'closure-mixed-captures': '''main=()=>{let shared=0 let private=0
let a=($capture @shared)=>{shared+=1 private+=1 return private}
let b=a
return if a()=?1 and b()=?1 and a()=?2 and shared=?3 and private=?0 42 else 1}''',
    'closure-nested-values': '''make=()=>{let n=0 return ()=>{n+=1 return ()=>{n+=10; n}}}
main=()=>{let outer=make() let other=outer let a=outer() let b=outer() let c=other()
return if a()=?11 and b()=?12 and c()=?11 and a()=?21 42 else 1}''',
    'closure-private-cell-copy': '''main=()=>{let n=0
let outer=()=>{let inner=($capture @n)=>{n+=1; n} return inner()}
let other=outer
return if outer()=?1 and other()=?1 and outer()=?2 and n=?0 42 else 1}''',
    'closure-container-copies': '''make=()=>{let n=0 return ()=>{n+=1; n}}
main=()=>{let a=[make()] let b=a let r=[call=make() rows=[a]] let q=r
if a[0]() not=?1 or b[0]() not=?1 or a[0]() not=?2 return 1
if r.call() not=?1 or q.call() not=?1 return 2
if r.rows[0][0]() not=?1 or q.rows[0][0]() not=?1 return 3
let m=["counter"->make()] let k=m
return if m["counter"]()=?1 and k["counter"]()=?1 42 else 4}''',
    'closure-dictionary-place': '''Counter:type=():>int64
make=()=>{let n=0 return ()=>{n+=1; n}}
advance=(@next:Counter)=>next()
main=()=>{let counters=["next"->make()]
if counters["next"]() not=?1 or counters["next"]() not=?1 return 1
if advance(@counters["next"]) not=?1 or advance(@counters["next"]) not=?2 return 2
let copy=counters
return if advance(@counters["next"])=?3 and advance(@copy["next"])=?3 42 else 3}''',
    'dictionary-reference-index-once': '''bump=(@n:int64)=>{n+=2}
main=()=>{let counts=["key"->40] let saved=counts let hits=0
let key=($capture @hits)=>{hits+=1; "key"}
bump(@counts[key()])
return if counts["key"]=?42 and saved["key"]=?40 and hits=?1 42 else 1}''',
    'closure-argument-values': '''Counter:type=():>int64
make=()=>{let n=0 return ()=>{n+=1; n}}
twice=(f:Counter)=>f()+f()
advance=(@f:Counter)=>f()
main=()=>{let a=make()
if twice(a) not=?3 or twice(a) not=?3 or a() not=?1 return 1
return if advance(@a)=?2 and a()=?3 42 else 2}''',
    'closure-const-snapshot': '''make=()=>{let n=0 return ()=>{n+=1; n}}
main=()=>{let a=make() const saved=a let b=saved
if a() not=?1 or a() not=?2 or saved() not=?1 or saved() not=?1 return 1
return if b()=?1 and b()=?2 42 else 2}''',
    'closure-wrapper-copy': '''make=()=>{let n=0 return (step:int64)=>{n+=step; n}}
main=()=>{let a=make() let p=(step:int64)=>a(step) let q=p
return if p(1)=?1 and q(2)=?2 and p(3)=?4 and a(1)=?1 42 else 1}''',
    'closure-local-replacement': '''make=(n:int64)=>{let value=n return (x:int64)=>{value+=x; value}}
main=()=>{let current=make(40)
let before=current({current=make(100); 2})
return if before=?42 and current(1)=?101 42 else 1}''',
    'closure-alias-replacement': '''Counter:type=(x:int64):>int64
make=(n:int64)=>{let value=n return (x:int64)=>{value+=x; value}}
replace=(@f:Counter)=>{f=make(100); 2}
main=()=>{let current=make(40)
let before=current(replace(@current))
return if before=?42 and current(1)=?101 42 else 1}''',
    'closure-self-replacement': '''Counter:type=(x:int64):>int64
let current:Counter
make=(n:int64)=>{let value=n return (x:int64)=>{value+=x; value}}
replace=()=>{current=make(100); 2}
main=()=>{current=make(40)
return if current(replace())=?42 and current(1)=?101 42 else 1}''',
    'closure-loop-values': '''make=()=>{let n=0 return ()=>{n+=1; n}}
main=()=>{let values=[make()] let total=0
loop f in values {total+=f()+f()}
return if total=?3 and values[0]()=?1 42 else 1}''',

    'numeric-scaled-magnitudes': '''main=()=>{
if abs(hypot(3e200 4e200)/5e200-1.0)>?1e-15 return 1
if abs(hypot(3e-200 4e-200)/5e-200-1.0)>?1e-15 return 2
if abs(norm([3e200 4e200])/5e200-1.0)>?1e-15 return 3
if abs(norm([3e-200 4e-200])/5e-200-1.0)>?1e-15 return 4
let tiny=f64_from_bits(1 as uint64)
if norm([tiny]) not=?tiny or hypot(tiny 0.0) not=?tiny return 5
return 42}''',
    'numeric-magnitude-special-values': '''main=()=>{
let empty:array<float64>=[]
if f64_bits(norm(empty)) not=?0 or f64_bits(norm([-0.0 0.0])) not=?0 return 1
if f64_bits(hypot(-0.0 -0.0)) not=?0 return 2
if hypot(NAN INF) not=?INF or hypot(-INF NAN) not=?INF return 3
if not is_nan(hypot(NAN 1.0)) or not is_nan(norm([NAN INF])) return 4
if norm([-INF 1.0]) not=?INF return 5
if f64_bits(abs(-0.0)) not=?0 or f32_bits(abs(f32_from_bits(0x80000000))) not=?0 return 6
if f64_bits(abs(f64_from_bits(0xfff8000000000042))) not=?0x7ff8000000000042 return 7
return 42}''',
    'game-camera-pointer-lock': '''import p"@lib/game/window.jo" as input
main=()=>{
input.__mouse_x=72.0 input.__mouse_y=48.0
input.__mouse_dx=640.0 input.__mouse_dy=400.0
mouse_lock(true)
if input.__mouse_dx not=?0.0 or input.__mouse_dy not=?0.0 return 1
input.__mouse_dx=4.0 input.__mouse_dy=-3.0
mouse_lock(true)
if input.__mouse_dx not=?4.0 or input.__mouse_dy not=?-3.0 return 2
mouse_lock(false)
if input.__mouse_dx not=?0.0 or input.__mouse_dy not=?0.0 return 3
input.__mouse_dx=-640.0 input.__mouse_dy=-400.0
input.__mouse_motion_reset()
return if input.__mouse_dx=?0.0 and input.__mouse_dy=?0.0
and input.__mouse_x=?72.0 and input.__mouse_y=?48.0 42 else 4}''',
    'numeric-grapheme-packed-words': '''main=()=>{
let words:array<uint8>=[99 120 86 52 18 128 255 255 255]
return if __grapheme_word(words 1) =? 305419896
and __grapheme_word(words 5) =? 4294967168 42 else 1}''',
    'array-comparison-conditional-empty': '''main=()=>{
let empty:array<string>=[] let values=["a"] let hits=0 let before=alloc_count()
loop i in [0..20) {
if values =? ["a"] and empty =? [] hits+=1
if false or empty not=? [] hits+=1000
if empty =? [] and values not=? [] hits+=1
}
return if hits =? 40 and alloc_count() =? before 42 else 1}''',
    'numeric-matrix-stepped-reshape': '''let m=reshape([loop i in [0..20) i] 4 5)
let rows=[3,1..0] let cols=[0,2..4]
right=()=>{rows=[0..0] cols=[1..1] m=reshape([loop i in [0..24) 100+i] 4 6) return [10 20 30]}
main=()=>{m[rows cols] .+= right()
let expected=[loop i in [0..24) 100+i]
expected[18]=25 expected[20]=37 expected[22]=49
expected[6]=15 expected[8]=27 expected[10]=39
return if m.shape =? [4 6] and m.data =? expected 42 else 1}''',
    'numeric-matrix-stepped-ranks': '''main=()=>{
let values=[loop i in [0..24) i] let reverse=[1,0..0]
let a=reshape(values 2 3 4)[reverse 1 [3,1..0]]
let b=reshape(values 2 2 2 3)[reverse 1 [..] [2,0..0]]
return if a.shape =? [2 2] and a.data =? [19 17 7 5]
and b.shape =? [2 2 2] and b.data =? [20 18 23 21 8 6 11 9] 42 else 1}''',
    'numeric-matrix-range-order': '''let trace=0 let m=reshape([loop i in [0..12) i] 3 4)
source=()=>{trace=trace*10+1 return m}
first=()=>{trace=trace*10+2 m=zeros<int64>(1 1) return 2}
second=()=>{trace=trace*10+3 return 0}
last=()=>{trace=trace*10+4 return 0}
columns=()=>{trace=trace*10+5 return [3,1..0]}
main=()=>{let out=source()[[first(),second()..last()] columns()]
return if trace =? 12345 and out.shape =? [2 2] and out.data =? [11 9 3 1]
and m.shape =? [1 1] 42 else 1}''',
    'numeric-matrix-stepped-read': '''main=()=>{
let m=reshape([loop i in [0..20) i] 4 5)
let selected=m[[3,1..0] [0,2..end]]
let reversed=m[2 [end,end-1..]]
return if selected.shape =? [2 3] and selected.data =? [15 17 19 5 7 9]
and reversed.shape =? [5] and reversed.data =? [14 13 12 11 10] 42 else 1}''',
    'numeric-matrix-stored-ranges': '''main=()=>{
let m=reshape([loop i in [0..20) i] 4 5)
let rows=[3,1..0] let cols=[0,2..5)
let selected=m[rows cols] let all_columns=m[rows]
let pair:array<IntRange>=[rows cols]
return if selected.shape =? [2 3] and selected.data =? [15 17 19 5 7 9]
and all_columns.shape =? [2 5] and all_columns.data =? [15 16 17 18 19 5 6 7 8 9]
and m[pair[0] pair[1]].data =? selected.data 42 else 1}''',
    'numeric-matrix-stepped-update': '''main=()=>{
let m=reshape([loop i in [0..20) i] 4 5) let saved=m
let rows=[3,1..0] let cols=[0,2..4]
m[rows cols] .+= [10 20 30]
m[0 [4,2..0]]=[100 200 300]
m[[2,0..0] 1]=99
return if m.data =? [300 99 200 3 100 15 6 27 8 39 10 99 12 13 14 25 16 37 18 49]
and saved.data =? [loop i in [0..20) i] 42 else 1}''',
    'numeric-matrix-exclusive-first': '''main=()=>{
let m=reshape([loop i in [0..20) i] 4 5)
let part=m[(0..3] (0,2..4]]
let reverse=m[(3,1..0] [..]]
return if part.shape =? [3 2] and part.data =? [7 9 12 14 17 19]
and reverse.shape =? [1 5] and reverse.data =? [5 6 7 8 9] 42 else 1}''',
    'numeric-matrix-stored-empty': '''main=()=>{
let m=reshape([loop i in [0..6) i] 2 3) let empty=[3..2]
let a=m[empty [..]] let b=m[[..] empty]
m[empty [..]] .+= [10 20 30]
let zero=zeros<int64>(0 3) let c=zero[[..] [2,0..0]]
return if a.shape =? [0 3] and b.shape =? [2 0] and c.shape =? [0 2]
and m.data =? [0 1 2 3 4 5] 42 else 1}''',
    'numeric-matrix-stepped-managed': '''work=():>void=>{
let m=reshape([["a"] ["b"] ["c"] ["d"] ["e"] ["f"]] 2 3) let saved=m
let rows=[1,0..0] let cols=[2,0..0]
let selected=m[rows cols] selected.data[0].push("!")
m[rows cols]=selected
assert(m.data =? [["a"] ["b"] ["c"] ["d"] ["e"] ["f" "!"]])
assert(saved.data =? [["a"] ["b"] ["c"] ["d"] ["e"] ["f"]])
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'sequence-extend-slices': '''main=()=>{
let source=[10 20 22 90] let out:array<int64>=[]
out.extend(source[1..3)) out.extend(source[4..]) out.extend(source[..0))
if out not=? [20 22] return 1
out.extend(source[2..end]) out.extend(source[..0])
return if out =? [20 22 22 90 10] and source =? [10 20 22 90] 42 else 2}''',
    'sequence-extend-self-slices': '''main=()=>{
let values=[10 20 22 90] values.reserve(64) let saved=values
values.extend(values[1..3))
if values not=? [10 20 22 90 20 22] or saved not=? [10 20 22 90] return 1
let small=[20 22] small.extend(small[..])
return if small =? [20 22 20 22] 42 else 2}''',
    'sequence-extend-self-slice-replaced': '''let values:array<array<int64>>=[]
lower=()=>{values=[[100]] return 1}
work=():>void=>{values=[[10] [20] [22] [90]] values.push([0])
values.extend(values[lower()..3))
assert(values =? [[100] [20] [22]]) values[1].push(42)
assert(values =? [[100] [20 42] [22]])}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'sequence-extend-slice-order': '''let source=[10 20 22 90]
let boxes:array<array<int64>>=[[]] let trace=0 let upper=3
get=()=>{trace=trace*10+1 return source}
lower=()=>{trace=trace*10+2 source=[100] return 1}
end_at=()=>{trace=trace*10+3 return upper}
choose=()=>{trace=trace*10+4 upper=0 boxes.push([99]) return 0}
main=()=>{boxes[choose()].extend(get()[lower()..end_at()))
return if trace =? 1234 and boxes =? [[20 22] [99]] and source =? [100] 42 else 1}''',
    'sequence-extend-slice-no-temporary': '''let source=[10 20 22 90]
let boxes:array<array<int64>>=[[]] let before=0
choose=()=>{assert(alloc_count() =? before) return 0}
main=()=>{boxes[0].reserve(4) before=alloc_count()
boxes[choose()].extend(source[1..3))
return if boxes[0] =? [20 22] and alloc_count() =? before 42 else 1}''',
    'sequence-extend-slice-managed': '''Item:type=[name:string values:array<int64>]
work=():>void=>{
let a=[Item["first" [20]] Item["second" [22]] Item["last" [99]]]
let saved=a let out:array<Item>=[] out.extend(a[..2))
a.extend(a[1..]) out[0].values.push(42) a[3].name="new"
assert(saved[0].values =? [20] and saved[1].name =? "second")
assert(out[0].values =? [20 42] and out[1].values =? [22])
assert(a[1].name =? "second" and a[3].values =? [22] and a.length =? 5)
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'fixed-array-extend-slice-snapshot': '''let source:array<array<int64> length=4>=[[10] [20] [22] [90]]
lower=()=>{source[1]=[99] return 1}
work=():>void=>{source=[[10] [20] [22] [90]]
let out:array<array<int64>>=[] out.extend(source[lower()..3))
out[0].push(42)
assert(out =? [[20 42] [22]] and source[1] =? [99])
let fixed:array<int64 length=1>=[99] let ints:array<int64>=[]
ints.extend(fixed[1..1)) assert(ints.length =? 0)
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'numeric-broadcast-matrix-selection': '''main=()=>{
let m=reshape([1 2 3 4 5 6 7 8 9 10 11 12] 3 4) let saved=m
m[[..] 1] .*= 2
m[1 [1..3)] .+= [10 20]
m[[1..2] [0..1]] .-= [1 2]
m[[0..0] [..]] .//= 2
return if m.shape =? [3 4] and m.data =? [0 2 1 2 4 20 27 8 8 18 11 12]
and saved.data =? [1 2 3 4 5 6 7 8 9 10 11 12] 42 else 1
}''',
    'numeric-broadcast-matrix-selection-reshape': '''let m=reshape([1 2 3 4] 2 2)
right=()=>{m=reshape([100 200 300 400 500 600] 2 3) return 10}
main=()=>{
m[[..] [..]] .+= right()
if m.shape not=? [2 3] or m.data not=? [11 12 300 13 14 600] return 1
m=reshape([1 2 3 4] 2 2)
m[0..0] .+= right()
return if m.shape =? [2 3] and m.data =? [11 12 300 400 500 600] 42 else 2
}''',
    'numeric-broadcast-matrix-selection-order': '''let boxes=[[matrix=reshape([1 2 3 4 5 6] 2 3)]]
let trace=0 let index=0
at=()=>{trace=trace*10+1 return index}
row=()=>{trace=trace*10+2 boxes[0].matrix=reshape([10 20 30 40 50 60] 2 3) return 1}
lower=()=>{trace=trace*10+3 return 1}
right=()=>{trace=trace*10+4 boxes.push([matrix=zeros<int64>(1 1)]) index=1 return 10}
main=()=>{let saved=boxes
boxes[at()].matrix[row() [lower()..end]] .+= right()
return if trace =? 1234 and boxes[0].matrix.data =? [10 20 30 40 15 16]
and saved[0].matrix.data =? [1 2 3 4 5 6] 42 else 1}''',
    'numeric-broadcast-matrix-selection-empty': '''main=()=>{
let a=zeros<int64>(0 3) a[[..] [..]] .+= [1 2 3]
let b=zeros<int64>(2 0) b[[..] [..]] .*= 2
let c=reshape([1 2 3 4] 2 2) c[[1..1) [..]] .+= 10
return if a.shape =? [0 3] and b.shape =? [2 0]
and a.data.length =? 0 and b.data.length =? 0 and c.data =? [1 2 3 4] 42 else 1
}''',
    'numeric-broadcast-matrix-selection-ranks': '''main=()=>{
let m=reshape([loop i in [0..24) i] 2 3 4) let saved=m
m[[..] end [0..end+1)] .+= [10 20 30 40]
loop i in [0..2) {loop j in [0..3) {loop k in [0..4) {
let expected=i*12+j*4+k+(if j =? 2 (k+1)*10 else 0)
if m[i j k] not=? expected return 1
}}}
let n=zeros<float32>(2 2 2 2) n[end [..] 0 [..]] .+= 2.5
return if saved[1 2 3] =? 23 and sum(n) =? 10.0 and n[1 1 0 1] =? 2.5 42 else 2
}''',
    'numeric-broadcast-matrix-selection-managed': '''work=()=>{
let m=reshape(["a" "b" "c" "d"] 2 2) let saved=m
m[[..] 1] .+= "!"
assert(m.data =? ["a" "b!" "c" "d!"] and saved.data =? ["a" "b" "c" "d"])
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'numeric-broadcast-selection-ranges': '''main=()=>{
let xs=[1 2 3 4 5 6] let saved=xs
xs[1..3] .+= 10
xs[5,3..] .*= 2
xs[0,2..4] .-= [1 2 3]
if xs not=? [0 24 11 28 2 12] or saved not=? [1 2 3 4 5 6] return 1
xs[..] .//= 2
xs[0..0) .+= 99
xs[[]] .+= 99
return if xs =? [0 12 5 14 1 6] 42 else 2
}''',
    'numeric-broadcast-selection-indices': '''main=()=>{
let xs=[1 2 3 4] let saved=xs
let positions=[0 2] xs[positions] .+= [10 20]
xs[[false true false true]] .*= 3
let span=[1,3..3] xs[span] .-= 1
xs[[0 0]] .+= [1 2]
let empty_mask:array<bool>=[] let empty:array<int64>=[]
empty[empty_mask] .+= 1 assert(empty.length =? 0)
return if xs =? [13 5 23 11] and saved =? [1 2 3 4] 42 else 1
}''',
    'numeric-broadcast-selection-fixed': '''main=()=>{
let xs:array<float32 length=4>=[1.0 2.0 3.0 4.0] let saved=xs
xs[1..] .*= 2.0 xs[[true false false true]] ./= 2.0
let indexes:array<int64 length=2>=[1 2] xs[indexes] .+= 0.5
return if xs =? [0.5 4.5 6.5 4.0] and saved =? [1.0 2.0 3.0 4.0] 42 else 1
}''',
    'numeric-broadcast-selection-place': '''let rows=[[1 2 3 4]] let index=0 let trace=0
at=()=>{trace=trace*10+1 return index}
lower=()=>{trace=trace*10+2 rows[0]=[10 20 30 40] return 1}
upper=()=>{trace=trace*10+3 return 3}
right=()=>{trace=trace*10+4 rows.push([99]) index=1 return 10}
main=()=>{let saved=rows
rows[at()][lower()..upper()) .+= right()
return if trace =? 1234 and rows =? [[10 12 13 40] [99]]
and saved =? [[1 2 3 4]] 42 else 1}''',
    'numeric-broadcast-selection-growth': '''let xs=[1 2 3]
right=()=>{xs.push(99) return 10}
main=()=>{xs[1..] .+= right()
return if xs =? [1 12 13 99] 42 else 1}''',
    'numeric-broadcast-selection-selector': '''let xs=[1 2 3] let mask=[true false true]
indexes=():>array<int64>=>{xs=[100 200 300] return [0 2]}
right=()=>{mask=[false true false] return 10}
main=()=>{
xs[indexes()] .+= 10
if xs not=? [11 200 13] return 1
xs[mask] .+= right()
return if xs =? [21 200 23] and mask =? [false true false] 42 else 2
}''',
    'numeric-broadcast-selection-custom': '''Box:type=[rows:array<array<int64>>]
let trace="" let index=0
__index__=(box:Box i:int64):>array<int64>=>{trace+="g" return box.rows[i]}
__setindex__=(@box:Box i:int64 value:array<int64>)=>{trace+="s" box.rows[i]=value}
at=()=>{trace+="i" return index}
right=()=>{trace+="r" index=1 return 10}
main=()=>{let box=Box[[[1 2 3] [4 5 6]]] let saved=box
box[at()][1..] .+= right()
return if box.rows =? [[1 12 13] [4 5 6]] and saved.rows =? [[1 2 3] [4 5 6]]
and trace =? "igrs" 42 else 1}''',
    'numeric-broadcast-selection-managed': '''work=()=>{
let xs=["a" "b" "c"] let saved=xs
xs[0,2..] .+= "!"
xs[[false true false]] .+= ["?"]
assert(xs =? ["a!" "b?" "c!"] and saved =? ["a" "b" "c"])
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'numeric-broadcast-selection-end': '''main=()=>{
let xs=[1 2 3 4 5] let saved=xs
xs[end,end-2..0] .+= 10
xs[0..end) .*= 2
return if xs =? [22 4 26 8 15] and saved =? [1 2 3 4 5] 42 else 1
}''',
    'comprehension-value-arrays': '''main=()=>{
let empty:array<int64>=[]
let a=[loop x in empty x*2]
let b=[loop x in [10 20 30] {let y=x+1 y*2}]
let fixed:array<int64 length=3>=[10 20 30]
let c=[loop x in fixed x+1]
let d=[loop i in 0.. and x in fixed i+x]
return if a.length =? 0 and b =? [22 42 62] and c =? [11 21 31]
and d =? [10 21 32] 42 else 1
}''',
    'comprehension-value-source-order': '''let values=[10 20 30] let trace=0
source=():>array<int64>=>{trace=trace*10+1 return values}
item=(x:int64)=>{trace=trace*10+2 values.clear() return x+1}
main=()=>{let result=[loop x in source() item(x)]
return if result =? [11 21 31] and values.length =? 0 and trace =? 1222 42 else 1}''',
    'comprehension-value-slice-order': '''let values=[99 20 22 100] let trace=0
source=():>array<int64>=>{trace=trace*10+1 return values}
lower=():>int64=>{trace=trace*10+2 values=[99] return 1}
upper=():>int64=>{trace=trace*10+3 return 3}
item=(x:int64)=>{trace=trace*10+4 return x}
main=()=>{let result=[loop x in source()[lower()..upper()) item(x)]
let empty=[loop x in result[1..1) x+1]
return if result =? [20 22] and empty.length =? 0 and trace =? 12344
and values =? [99] 42 else 1}''',
    'comprehension-value-managed': '''copy=(xs:array<int64>):>array<int64>=>xs
work=()=>{
let source=[[20] [22]] let saved=source
let result=[loop xs in source copy(xs)]
source[0][0]=99 result[1].push(100)
assert(result =? [[20] [22 100]] and saved =? [[20] [22]])
let fixed:array<array<int64> length=2>=[[20] [22]]
let mapped=[loop xs in fixed {let local=copy(xs) copy(local)}]
mapped[0].push(1) assert(fixed[0] =? [20] and mapped[1] =? [22])
let pairs=[loop i in 0.. and xs in source i->xs] let old=pairs
pairs[0].push(1) assert(old[0] =? [99])
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'comprehension-value-bindings': '''bump=(@i:int64 x:int64)=>{i+=10 return i+x}
change=(@x:int64)=>{x+=1 return x}
main=()=>{
let values=[10 20 30]
let indexed=[loop i in 0.. and x in values bump(@i x)]
let edited=[loop x in values {let local=x change(@local)}]
return if indexed =? [20 31 42] and edited =? [11 21 31]
and values =? [10 20 30] 42 else 1
}''',
    'comprehension-value-control-fallback': '''first=(xs:array<int64>):>array<int64>=>{
let result=[loop x in xs {let y={if x >? 2 return [99] x+10} y}]
return result
}
main=()=>{
let a=[loop x in [1 2 3 4] {if x >? 2 break x}]
let b=[loop x in [1 2 3 4] {if x%2 =? 0 continue x}]
let c=[loop x in [1 2] {let y=if x =? 1 20 else 22 y}]
return if a =? [1 2] and b =? [1 3] and c =? [20 22]
and first([1 2 3]) =? [99] 42 else 1
}''',
    'comprehension-reserved-records': '''Point:type=[x:int64 y:float64]
main=()=>{
let points=[loop i in [0..17) Point[i (i as float64)*0.5]] let saved=points
points[0].x=99
if saved[0].x not=? 0 or points[1].x not=? 1 return 1
loop i in [0..17) {if saved[i].x not=? i or saved[i].y not=? (i as float64)*0.5 return 2}
return 42
}''',
    'comprehension-reserved-bounds': '''let calls=0
value=(i:int64)=>{calls+=1 return i}
main=()=>{
let bound:int64=-3
let negative=[loop i in [0..bound) value(i)]
let empty=[loop i in [0..0) value(i)]
if calls not=? 0 or negative.length not=? 0 or empty.length not=? 0 return 1
let small:uint8=3 let unsigned:uint64=3
let a=[loop i in [0..small) i] let b=[loop i in [0..unsigned) i]
return if a =? [0 1 2] and b =? [0 1 2] 42 else 2
}''',
    'comprehension-reserved-order': '''let bound=3 let reads=0 let visited:array<int64>=[]
limit=()=>{reads+=1 return bound}
value=(i:int64)=>{bound=0 visited.push(i) return i*7}
main=()=>{let result=[loop i in [0..limit()) value(i)]
return if result =? [0 7 14] and visited =? [0 1 2] and reads =? 1 and bound =? 0 42 else 1}''',
    'comprehension-reserved-counter': '''bump=(@i:int64)=>{i+=10 return i}
main=()=>{let result=[loop i in [0..3) bump(@i)]
return if result =? [10 11 12] 42 else 1}''',
    'comprehension-reserved-managed': '''make=(i:int64)=>["left" "right"]
work=()=>{
let rows=[loop i in [0..17) make(i)] let saved=rows
rows[0].push("new")
assert(rows[1] =? ["left" "right"] and saved[0] =? ["left" "right"])
let pairs=[loop i in [0..17) i->[i i+1]] let old=pairs
pairs[0][0]=99 assert(old[0] =? [0 1])
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'comprehension-reserved-control-fallback': '''main=()=>{
let result=[loop i in [0..int64.max) {if i >=? 3 break i}]
let skipped=[loop i in [0..7) {if i%2 =? 0 continue i}]
let nested=[loop i in [0..3) [loop j in [0..2) i*10+j]]
return if result =? [0 1 2] and skipped =? [1 3 5]
and nested =? [[0 1] [10 11] [20 21]] 42 else 1
}''',
    'comprehension-broadcast-statement': '''main=()=>{
let xs=[1 2]
let empty:array<int64>=[loop i in [0..3) {xs .+= i}]
return if empty.length =? 0 and xs =? [4 5] 42 else 1
}''',
    'numeric-broadcast-update-custom-index': '''Box:type=[values:array<array<int64>>]
let trace="" let index=0
__index__=(box:Box i:int64):>array<int64>=>{trace+="g" return box.values[i]}
__setindex__=(@box:Box i:int64 value:array<int64>)=>{trace+="s" box.values[i]=value}
at=()=>{trace+="i" return index}
right=()=>{trace+="r" index=1 return [10]}
main=()=>{let box=Box[[[1 2] [3 4]]] let saved=box
box[at()] .+= right()
return if box.values =? [[11 12] [3 4]] and saved.values =? [[1 2] [3 4]]
and trace =? "igrs" 42 else 1}''',
    'numeric-broadcast-update-reference': '''edit=(@xs:array<int64> amount:int64)=>{xs .+= amount}
main=()=>{
let xs=[1 2] let saved=xs edit(@xs 40)
if xs not=? [41 42] or saved not=? [1 2] return 1
let m=reshape([10 20] 2 1) let old=m
m .+= [1 2 3]
return if m.shape =? [2 3] and m.data =? [11 12 13 21 22 23]
and old.shape =? [2 1] and old.data =? [10 20] 42 else 2
}''',
    'numeric-broadcast-update': '''main=()=>{
let xs=[1 2 3] let saved=xs
xs .+= [10] xs .*= 2 xs .-= 1 xs .^= 2
if xs not=? [441 529 625] or saved not=? [1 2 3] return 1
xs .//= 20 xs .%= 7
if xs not=? [1 5 3] return 2
let floats=[1.0 2.0 3.0] floats ./= 2.0
if floats not=? [0.5 1.0 1.5] return 3
let fractions=[1/2 3/2] fractions ./= 2
if fractions not=? [1/4 3/4] return 4
let scalar=20 scalar .+= 22
return if scalar =? 42 42 else 5
}''',
    'numeric-broadcast-update-matrix': '''main=()=>{
let m=reshape([1 2 3 4 5 6] 2 3) let saved=m
m .*= [10 20 30] m .+= reshape([100 200] 2 1)
if m.data not=? [110 140 190 240 300 380] return 1
let row:array<float32 length=3>=[1 2 3] let old=row
let one:array<float32>=[1.0]
row .*= 2.0 row .+= one
return if row =? [3.0 5.0 7.0] and old =? [1.0 2.0 3.0]
and saved.data =? [1 2 3 4 5 6] 42 else 2
}''',
    'numeric-broadcast-update-place': '''Box:type=[values:array<int64>]
main=()=>{
let rows=[Box[[1 2]] Box[[3 4]]] let saved=rows
let which=0 let calls=0
index=($capture @calls $capture @which)=>{calls+=1 return which}
amount=($capture @which $capture @rows)=>{which=1 rows.push(Box[[5 6]]) return 10}
rows[index()].values .+= amount()
if calls not=? 1 or rows[0].values not=? [11 12] or rows[1].values not=? [3 4] return 1
if rows.length not=? 3 or saved[0].values not=? [1 2] return 2
let m:dict<string array<int64>>=["a"->[1 2]] let old=m
m["a"] .*= [10 20]
return if m["a"] =? [10 40] and old["a"] =? [1 2] 42 else 3
}''',
    'numeric-broadcast-update-self': '''main=()=>{
let xs=[1 2 3] let saved=xs
xs .+= xs .* 2
if xs not=? [3 6 9] or saved not=? [1 2 3] return 1
let rows=[[1 2] [3 4]] let old=rows
rows[end] .*= rows[0]
let strings=["a" "b"] let words=strings
strings .+= "!"
return if rows =? [[1 2] [3 8]] and old =? [[1 2] [3 4]]
and strings =? ["a!" "b!"] and words =? ["a" "b"] 42 else 2
}''',
    'numeric-broadcast-unordered': '''main=()=>{
let zero:float64=0.0 let nan=zero/zero let xs=[nan 1.0]
if (xs .not<? 2.0) not=? [true false] return 1
if (xs .not<=? 2.0) not=? [true false] return 2
if (xs .not>? 2.0) not=? [true true] return 3
if (xs .not>=? 2.0) not=? [true true] return 4
if (xs .not=? xs) not=? [true false] return 5
return 42
}''',
    'numeric-broadcast-fixed': '''main=()=>{
let xs:array<float32 length=3>=[1 2 3] let saved=xs
let result=xs .* 2 .+ 1
if result not=? [3.0 5.0 7.0] or xs not=? saved return 1
let words:array<string length=2>=["a" "b"]
let decorate=(s:string)=>s+"!"
return if decorate.(words) =? ["a!" "b!"] 42 else 2
}''',
    'numeric-broadcast-arithmetic': '''main=()=>{
let xs=[1 2 3] let saved=xs
let ys=xs .* 2 .+ [10] .- 1
if ys not=? [11 13 15] or xs not=? saved return 1
if (2 .* xs .^ 2) not=? [2 8 18] return 2
if ([2] .^ [3] .^ [2]) not=? [512] return 3
if (xs .+ 1) .* (xs .- 1) not=? [0 3 8] return 4
if (20 .+ 22) not=? 42 return 5
return 42
}''',
    'numeric-broadcast-unary': '''main=()=>{
let xs=[1 -2 3] let saved=xs
let negated=.-xs let positive=.+xs
if negated not=?[-1 2 -3] or positive not=?xs return 1
negated[0]=99 positive[1]=99
if xs not=?saved return 2
if (.-(xs .+ 1) .* 2) not=?[-4 2 -8] return 3
if (.-xs .^ 2) not=?[-1 -4 -9] return 4
if (.- .-xs) not=?xs or (.+42) not=?42 or (.-42) not=? -42 return 5
return 42}''',
    'numeric-broadcast-unary-shapes': '''main=()=>{
let fixed:array<int64 length=3>=[1 -2 3]
let result:array<int64>=.-fixed
if result not=?[-1 2 -3] return 1
let matrix=reshape([1 2 3 4 5 6] 2 3)
let changed=.-(matrix .+ [10 20 30])
if changed.shape not=?[2 3] or changed.data not=?[-11 -22 -33 -14 -25 -36] return 2
let empty:array<int64>=[]
if (.-empty).length not=?0 or (.+empty).length not=?0 return 3
let empty_matrix=.-zeros<int64>(0 3)
if empty_matrix.shape not=?[0 3] or empty_matrix.data.length not=?0 return 4
return 42}''',
    'numeric-broadcast-unary-floats': '''main=()=>{
let values:array<float64>=[0.0 -0.0 1.5 -2.0 0.0/0.0]
let negated=.-values let positive=.+values
if not (1.0/negated[0] <? 0.0) or not (1.0/negated[1] >? 0.0) return 1
if not (1.0/positive[0] >? 0.0) or not (1.0/positive[1] <? 0.0) return 2
if negated[2] not=? -1.5 or negated[3] not=?2.0 return 3
if negated[4]=?negated[4] or positive[4]=?positive[4] return 4
let small:array<float32>=[0.0 -0.0 1.5]
let flipped=.-small
return if 1.0/flipped[0] <? 0.0 and 1.0/flipped[1] >? 0.0 and flipped[2]=? -1.5 42 else 5}''',
    'numeric-broadcast-unary-custom-order': '''Number:type=[value:int64 label:string]
let trace=0
source=()=>{trace=trace*10+1 return [Number[2 "a"] Number[3 "b"]]}
offset=()=>{trace=trace*10+4 return 10}
extract=(value:Number):>int64=>value.value
__unary_sub__=(value:Number):>Number=>{
trace=trace*10+value.value
return Number[-value.value value.label]
}
main=()=>{
let values=.-source()
if trace not=?123 or values not=?[Number[-2 "a"] Number[-3 "b"]] return 1
trace=0
let fused=extract.(.-source()) .+ offset()
if trace not=?1423 or fused not=?[8 7] return 3
let saved=values values[0].label="changed"
return if saved[0].label=?"a" 42 else 2}''',
    'numeric-broadcast-division': '''main=()=>{
let xs=[-7 7 -7 7] let ys=[2 2 -2 -2]
if (xs .// ys) not=? [-4 3 3 -4] return 1
if (xs .% ys) not=? [1 1 -1 -1] return 2
let fractions=xs ./ ys
if fractions[0] not=? -7/2 or fractions[1] not=? 7/2 return 3
if fractions[2] not=? 7/2 or fractions[3] not=? -7/2 return 4
if ([1.0 2.0 3.0] ./ 2.0) not=? [0.5 1.0 1.5] return 5
return 42
}''',
    'numeric-broadcast-comparisons': '''main=()=>{
let xs=[1 2 3]
if (xs .=? 2) not=? [false true false] return 1
if (xs .not=? 2) not=? [true false true] return 2
if (xs .<? 2) not=? [true false false] return 3
if (xs .<=? 2) not=? [true true false] return 4
if (xs .>? 2) not=? [false false true] return 5
if (xs .>=? 2) not=? [false true true] return 6
if (xs .not<? 2) not=? [false true true] return 7
if (xs .not<=? 2) not=? [false false true] return 8
if (xs .not>? 2) not=? [true true false] return 9
if (xs .not>=? 2) not=? [true false false] return 10
return 42
}''',
    'numeric-broadcast-functions': '''square=(x:float64)=>x*x
blend=(x:float64 y:float64 scale:float64)=>x+y*scale
main=()=>{
let xs=[1.0 4.0 9.0]
if sqrt.(xs) not=? [1.0 2.0 3.0] return 1
if square.(sqrt.(xs) .+ 1.0) not=? [4.0 9.0 16.0] return 2
if blend.(xs [2.0] 0.5) not=? [2.0 5.0 10.0] return 3
let offset=3.0 let shift=(x:float64)=>x+offset
if shift.(xs) not=? [4.0 7.0 12.0] return 4
return 42
}''',
    'numeric-broadcast-shapes': '''main=()=>{
let m=reshape([1 2 3 4 5 6] 2 3)
let row=[10 20 30] let col=reshape([100 200] 2 1)
let result=m .+ row .+ col
if result.shape not=? [2 3] or result.data not=? [111 122 133 214 225 236] return 1
let outer=col .* row
if outer.shape not=? [2 3] or outer.data not=? [1000 2000 3000 2000 4000 6000] return 2
let volume=reshape([1 2 3 4 5 6 7 8] 2 2 2) .* [1 10]
if volume.shape not=? [2 2 2] or volume.data not=? [1 20 3 40 5 60 7 80] return 3
let mask=m .>? 3
if mask.data not=? [false false false true true true] return 4
result[0 0]=99
return if m.data =? [1 2 3 4 5 6] and row =? [10 20 30] 42 else 5
}''',
    'numeric-broadcast-empty': '''main=()=>{
let xs:array<float64>=[]
if (xs .* 2.0 .+ [1.0]).length not=? 0 return 1
if sqrt.(xs).length not=? 0 return 2
let result=zeros(0 3) .+ [1.0 2.0 3.0]
if result.shape not=? [0 3] or size(result) not=? 0 return 3
let other=zeros(2 0) .+ reshape([10.0 20.0] 2 1)
return if other.shape =? [2 0] and size(other) =? 0 42 else 4
}''',
    'numeric-broadcast-order': '''let trace:int64=0
values=(tag:int64)=>{trace=trace*10+tag return [1 2 3]}
scalar=()=>{trace=trace*10+3 return 2}
main=()=>{
let result=values(1) .+ values(2) .* scalar()
if trace not=? 123 or result not=? [3 6 9] return 1
let seen:array<int64>=[]
visit=($capture @seen x:int64)=>{seen.push(x) return x+1}
let visited=visit.([1 2 3])
return if visited =? [2 3 4] and seen =? [1 2 3] 42 else 2
}''',
    'numeric-broadcast-managed': '''wrap=(text:string)=>[text "!"]
work=()=>{
let rows=wrap.(["a" "b" "c"]) let saved=rows
rows[0].push("changed")
assert(saved =? [["a" "!"] ["b" "!"] ["c" "!"]])
assert(rows[0] =? ["a" "!" "changed"])
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'format-argument-order': '''let word="first"
spec=():>string=>{word="later" return ">8"}
main=()=>{
let result=format(word spec())
if result not=? "   first" or word not=? "later" return 1
let pattern=".2f"
if format(1.125 pattern) not=? "1.12" return 2
return 42
}''',
    'game-chart-series': '''main=()=>{
let c=Chart[equal_axes=true legend_at=LegendAt.bottom_left]
let xs=[0 1 2] let ys=[3 4 5]
c.line(xs ys "integer" dash=2.1)
xs[0]=99 ys[1]=99
let floats:array<float32>=[0.5 1.5 2.5]
c.points(floats floats "custom" color=RED)
c.annotate(100.0 100.0 "note")
c.bars(["a" "b" "c"] floats "float32")
c.line([1.0 2.0] "float64")
c.line(floats "float32 line")
c.points([0 1] [2 3] "integer points")
c.bars(["a" "b"] [10 20] "integer bars")
if c.series[0].xs[0] not=?0.0 or c.series[0].ys[1] not=?4.0 return 1
if c.series[0].dash not=?2.1 return 2
if c.series[1].ys[0] not=?0.5 or c.series[1].color not=?RED return 3
if c.series[0].color not=?CHART_COLORS[0] return 4
if c.series[3].color not=?CHART_COLORS[1] return 5
if c.series[4].color not=?CHART_COLORS[2] return 6
if c.series[5].xs not=?[0.0 1.0 2.0] return 7
if c.series[2].name not=?"note" return 8
return 42
}''',
    'game-font-math': '''import p"@lib/game/draw2d.jo" as surface
main=()=>{
surface.__font_init()
loop code in [0x03B8 0x03C0 0x0394 0x2212 0x221A 0x2248 0x2260 0x2264 0x2265 0x221E
              0x2211 0x222B 0x2202 0x221D 0x22C5 0x2207 0x2208 0x2192 0x2080 0x2074 0x2713 0x2717] {
    if surface.__glyph(surface.__default_font code) <? 0 return 1
}
if text_width("θ π Δ − √ ≈ ≠ ≤ ≥ ∞ ∑ ∫ ∂ ∝ ⋅ ∇ ∈ → x₀ x⁴ ✓ ✗") <=? 0 return 2
return 42
}''',
    'game-shadow-defaults': '''main=()=>{
let params=LitParams[]
if params.shadow_texel not=? f32(1.0/2048.0) or params.shadow_taps not=? 9.0 return 1
return 42
}''',
    'record-top-level-updates': '''Pair:type=[left:int64 right:int64]
let pair=Pair[1 2]
let values=[10 20]
pair.left=20
values[1]=22
counter=1
read=()=>counter
counter=40
main=()=>if pair.left+values[1] =? 42 and read() =? 40 42 else 1''',
    'unpack-top-level-updates': '''[left right]=[1 2]
[left right]=[20 22]
main=()=>left+right''',
    'game-polyline-joins': '''import p"@lib/game/draw2d.jo" as surface
vertex=(buffer:array<float32> i:int64):>vec2=>vec2(buffer[i*9] buffer[i*9+1])
work=(buffer:array<float32>):>int64=>{
polyline([vec2(10 10) vec2(100 10) vec2(100 100)] 10 WHITE)
if surface.__b_count not=? 12 return 1
if vertex(buffer 1) not=? vertex(buffer 6) or vertex(buffer 2) not=? vertex(buffer 11) return 2
if vertex(buffer 1) not=? vec2(94 16) or vertex(buffer 2) not=? vec2(106 4) return 3
surface.__b_count=0
polyline([vec2(10 10) vec2(100 10) vec2(100 10) vec2(100 100) vec2(10 10)] 10 WHITE closed=true)
if surface.__b_count not=? 18 return 4
if vertex(buffer 0) not=? vertex(buffer 13) or vertex(buffer 5) not=? vertex(buffer 14) return 5
return 42}
main=()=>{let buffer:array<float32>=[] buffer.resize(18*9)
let previous=surface.__b_buf
surface.__b_buf=buffer.data() surface.__b_tex=surface.__white.id surface.__b_count=0
let result=work(buffer) surface.__b_buf=previous surface.__b_count=0
return result}''',
    'game-polyline-degenerate': '''import p"@lib/game/draw2d.jo" as surface
work=(buffer:array<float32>):>int64=>{
polyline([] 10 WHITE) polyline([vec2(10 10)] 10 WHITE)
polyline([vec2(10 10) vec2(10 10) vec2(10 10)] 10 WHITE closed=true)
if surface.__b_count not=? 0 return 1
polyline([vec2(10 10) vec2(100 10) vec2(100 10)] 10 WHITE closed=true)
if surface.__b_count not=? 6 return 2
surface.__b_count=0
polyline([vec2(0 0) vec2(100 0) vec2(1 1)] 10 WHITE)
let offset=vec2(buffer[9] buffer[10])-vec2(100 0)
if not (length(offset) <=? 18) return 3
surface.__b_count=0
polyline([vec2(0 0) vec2(100 0) vec2(0 0)] 10 WHITE)
loop i in [0..surface.__b_count) {
if not (abs(buffer[i*9]) <=? 106) or not (abs(buffer[i*9+1]) <=? 6) return 4}
return 42}
main=()=>{let buffer:array<float32>=[] buffer.resize(18*9)
let previous=surface.__b_buf
surface.__b_buf=buffer.data() surface.__b_tex=surface.__white.id surface.__b_count=0
let before=alloc_count() let result=work(buffer)
if alloc_count() not=? before result=5
surface.__b_buf=previous surface.__b_count=0
return result}''',
    'game-polyline-batches': '''import p"@lib/game/draw2d.jo" as surface
main=()=>{let points:array<vec2>=[] loop i in [0..3000) {points.push(vec2(i as float32 (i%2) as float32))}
let buffer:array<float32>=[] buffer.resize(points.length*6*9)
let previous=surface.__b_buf let previous_effect=surface.__fx_draw let previous_on=surface.__fx_on
surface.__b_buf=buffer.data() surface.__b_tex=surface.__white.id surface.__b_count=0
let seen:int64=0 let batches:int64=0
let baseline:int64=0
surface.__fx_on=true
surface.__fx_draw=($capture @seen $capture @batches $capture @baseline $capture @points):>void=>{
if surface.__b_count >? surface.__BATCH_MAX panic("polyline exceeded its vertex batch")
if batches =? 0 and alloc_count() not=? baseline panic("polyline allocated scratch buffers")
seen+=surface.__b_count batches+=1
if batches =? 1 points.clear()}
baseline=alloc_count()
polyline(points 2 WHITE) surface.flush()
surface.__fx_draw=previous_effect surface.__fx_on=previous_on surface.__b_buf=previous
return if seen =? 2999*6 and batches =? 2 and points.length =? 0 42 else 1}''',
    'game-camera-roll': '''import p"@lib/game/draw2d.jo" as surface
main=()=>{
surface.__target_w=1280 surface.__target_h=720
let eye=vec3(0 0 5) let target=vec3(0 0 0) let point=vec3(1 0 0)
camera3d(eye target)
let center=world_to_screen(target) let normal=world_to_screen(point)
if center is? none or normal is? none return 1
if normal.x<=?center.x or abs(normal.y-center.y)>?0.01 return 2
camera3d(eye target up=vec3(1 0 0))
let rolled=world_to_screen(point)
if rolled is? none return 3
if abs(rolled.x-center.x)>?0.01 or rolled.y>=?center.y return 4
let [origin direction]=screen_ray(rolled)
if dot(normalize(point-origin) direction)<?0.9999 return 5
if world_to_screen(vec3(0 0 6)) isnt? none return 6
camera3d(eye target)
let restored=world_to_screen(point)
return if restored isnt? none and length(restored-normal)<?0.01 42 else 7}''',
    'game-camera-audio': '''from p"@lib/game/audio.jo" import __place_3d
main=()=>{
let eye=vec3(0 0 5) let point=vec3(1 0 5)
camera3d(eye vec3(0 0 0))
let [gain normal]=__place_3d(point 40.0)
camera3d(eye vec3(0 0 0) up=vec3(0 -1 0))
let [rolledGain rolled]=__place_3d(point 40.0)
camera3d(eye vec3(0 0 0))
return if normal>?0.79 and rolled<?-0.79 and abs(gain-rolledGain)<?0.0001 42 else 1}''',

    'generic-constructor-collections': '''Box:type=<T>[value:T]
main=()=>{
let numbers=Box([20 22]) let words=Box(["hello" "world"])
let record=Box([x=20 y=22]) let keys=Box(["answer"->42])
let members=Box(set[20 22])
if words.value[1] not=?"world" or keys.value["answer"] not=?42 return 1
if not members.value.contains(20) or record.value.x+record.value.y not=?42 return 2
return numbers.value[0]+numbers.value[1]}''',
    'generic-constructor-empty-inference': '''Box:type=<T>[value:T]
Batch:type=<T>[items:array<T> exemplar:T]
main=()=>{
let numbers=Box([]) numbers.value.push(40)
let words=Box([]) words.value.push("hi")
let empty=Batch([] 42) let narrow=Batch([20 22] (0 as uint8))
let saved=numbers numbers.value[0]=99
let fixed=Box([40])
if saved not=?fixed or empty.items.length not=?0 or empty.exemplar not=?42 return 1
if (narrow.items[0] as int64)+(narrow.items[1] as int64) not=?42 return 2
return saved.value[0]+words.value[0].length}''',
    'generic-constructor-callbacks': '''Transform:type=<T U>[value:T step:((x:T):>U)]
Runner:type=<T>[value:T step:((x:T):>T)]
Box:type=<T>[value:T]
identity=<T>(value:T):>T=>value
main=()=>{
let transform=Transform(20 (x)=>x+22)
let format=Transform(42 (x)=>"value={x}")
let function=Box((x:int64)=>x+2)
let runner=Runner(42 identity)
return if transform.step(transform.value)=?42 and format.step(format.value)=?"value=42"
and function.value(40)=?42 and runner.step(runner.value)=?42 42 else 1}''',
    'generic-constructor-argument-order': '''Pair:type=<A B>[left:A right:B]
let trace:int64=0
mark=(value:int64):>int64=>{trace=trace*10+value return value}
main=()=>{
let pair=Pair(right=[mark(2)] left=[item=mark(1)])
return if trace=?21 and pair.left.item=?1 and pair.right[0]=?2 42 else 1}''',
    'generic-constructor-imported': ('from p"'+(Path(__file__).resolve().parents[2] / 'core/tests/hash_keys.dewy').as_posix()+'" import Tagged\n'+'''main=()=>{
let value=Tagged([20 22] "kept") let copied=value
value.value[0]=99
return copied.value[0]+copied.value[1]}'''),
    'generic-record-ordered-arguments': '''Box:type=<T>[value:T]
Pair:type=<A B>[left:A right:B]
score=(box:Box<array<int64>>):>int64=>box.value[0]
score=(box:Box<array<string>>):>int64=>box.value[0].length
main=()=>{
let numbers=Box<array<int64>>[[40]]
let words=Box<array<string>>[["hi"]]
let fixed=Box<array<int64>>[[20 22]]
let pair=Pair(numbers words) let reversed=Pair(words numbers)
let saved=numbers numbers.value[0]=99
if fixed.value[0]+fixed.value[1] not=?42 or saved.value[0] not=?40 return 1
return if reversed.left.value[0]=?"hi" and reversed.right.value[0]=?40
score(pair.left)+score(pair.right) else 2}''',
    'generic-record-recursive-storage': '''Node:type=<T>[value:T children:array<Node<T>>=[]]
sum=<T>(node:Node<T>):>T=>{
let result=node.value loop child in node.children {result+=sum(child)} return result}
main=()=>{
let tree=Node<int64>[20 [Node<int64>[10] Node<int64>[12]]]
let strings=Node<string>["a" [Node<string>["b"]]]
let saved=tree tree.children[0].value=99
return if sum(strings)=?"ab" and sum(saved)=?42 and sum(tree)=?131 42 else 1}''',
    'constant-local-once': '''let calls=0
next=()=>{calls+=1 return calls}
main=()=>{const first=next() let a=first let b=first const unused=next()
return if a=?1 and b=?1 and calls=?2 42 else 1}''',
    'constant-global-once': '''let calls=0
next=()=>{calls+=1 return calls}
const first=next()
const unused=next()
main=()=>if first=?1 and first=?1 and calls=?2 42 else 1''',
    'constant-scalar-snapshot': '''main=()=>{let source=20 const saved=source source=99
return saved+saved+2}''',
    'constant-managed-snapshot': '''main=()=>{
let source=[items=[20 22] names=["a"->"before"]]
const saved=source
source.items[0]=99 source.names["a"]="after"
let copy=saved copy.items[0]=0
return if saved.items=?[20 22] and saved.names["a"]=?"before" and copy.items[0]=?0 42 else 1}''',
    'constant-closure-snapshot': '''make=()=>{let source=[20 22] const saved=source
let read=()=>saved source[0]=99 return read}
main=()=>{let read=make() let copy=read() copy[0]=0
return if read()=?[20 22] 42 else 1}''',
    'constant-parameter-snapshot': '''take=(@source:array<int64>)=>{const saved=source source[0]=99 return saved[0]}
main=()=>{let source=[20 22] return if take(@source)=?20 and source[0]=?99 42 else 1}''',
    'constant-callable-once': '''let calls=0
make=()=>{calls+=1 let n=40 return ()=>{n+=1 return n}}
main=()=>{const next=make() let a=next() let b=next()
return if calls=?1 and a=?41 and b=?41 42 else 1}''',
    'constant-loop-initialization': '''let calls=0
next=()=>{calls+=1 return calls}
main=()=>{let total=0 loop i in [0..3) {const value=next() total+=value+value}
return if total=?12 and calls=?3 42 else 1}''',
    'constant-array-length': '''const BASE=1
const WIDTH=BASE+1
Pair:type=array<int64 length=WIDTH>
main=()=>{const width=WIDTH const width2=width let values:array<int64 length=width2>=[20 22]
let other:Pair=values return other[0]+other[1]}''',
    'constant-array-length-shadow': '''main=()=>{
const base=1 const width=base+1
let base=7 let values:array<int64 length=width>=[20 22]
return values[0]+values[1]}''',
    'numeric-matrix-annotations': '''identity=(m:NDArray<float64>):>NDArray<float64>=>m
main=()=>{
let original=zeros(2 3) let copied=identity(original)
copied[1 2]=42.0
assert(sum(original) =? 0.0 and sum(copied) =? 42.0)
let boxed:array<NDArray<float64>>=[original copied]
let maybe:NDArray<float64>?=boxed[1]
if maybe is? none return 1
return maybe[1 2] as int64}''',
    'numeric-matrix-end': '''main=()=>{
let m=reshape([1 2 3 4 5 6] 2 3)
assert(m[end end] =? 6 and m[0 end] =? 3 and m[end 0] =? 4)
assert(m[end-1 end] =? 3)
assert(m[0 [0..end]].data =? [1 2 3])
assert(m[[0..end] end].data =? [3 6])
assert(m[[0..end] [0..end]].data =? m.data)
let saved=m m[end end]=42
assert(m.data =? [1 2 3 4 5 42] and saved.data =? [1 2 3 4 5 6])
m[0 end]+=10
assert(m[0 end] =? 13)
m[[0..end] end]=[20 22]
assert(m.data =? [1 2 20 4 5 22])
return 42}''',
    'numeric-matrix-end-ranks': '''main=()=>{
let m=reshape([loop i in [0..24) i] 2 3 4)
assert(m[end end end] =? 23 and m[0 end end] =? 11)
assert(m[[..] end end].data =? [11 23])
let n=zeros(2 3 4 5) n[end end end end]=42.0
assert(n[1 2 3 4] =? 42.0 and sum(n) =? 42.0)
return 42}''',
    'numeric-matrix-end-empty': '''main=()=>{
let m=zeros(2 0)
let part=m[[0..end+1) [0..end+1)]
assert(part.shape =? [2 0] and size(part) =? 0)
m[[0..end+1) [0..end+1)]=[]
assert(size(m) =? 0)
return 42}''',
    'numeric-matrix-end-place': '''let calls=0
pick=()=>{calls+=1 return 0}
main=()=>{
let boxes=[[matrix=reshape([1 2 3 4 5 6] 2 3)]] let saved=boxes
boxes[pick()].matrix[end end]=42
assert(calls =? 1 and boxes[0].matrix[1 2] =? 42)
assert(saved[0].matrix[1 2] =? 6)
boxes[pick()].matrix[[..] end]=[20 22]
assert(calls =? 2 and boxes[0].matrix[[..] 2].data =? [20 22])
return 42}''',
    'numeric-matrix-end-evaluation': '''let m=reshape([1 2 3 4 5 6] 2 3)
let calls=0
source=()=>{calls+=1 return m}
change=()=>{m=zeros<int64>(4 5) return 0}
main=()=>{
let value=source()[change() end]
assert(value =? 3 and calls =? 1 and m.shape =? [4 5])
return 42}''',
    'numeric-matrix-slices': '''main=()=>{
let a=reshape([1 2 3 4 5 6] 2 3)
assert(a[[..] 1].shape =? [2] and a[[..] 1].data =? [2 5])
assert(a[1 [..]].shape =? [3] and a[1 [..]].data =? [4 5 6])
let block=a[[0..2) [1..3)]
assert(block.shape =? [2 2] and block.data =? [2 3 5 6])
assert(a[0 [1..]].data =? [2 3])
assert(a[[..] [..]].data =? a.data)
assert(a[[0..0) [..]].shape =? [0 3] and size(a[[0..0) [..]]) =? 0)
return 42}''',
    'numeric-matrix-slice-updates': '''main=()=>{
let a=reshape([1 2 3 4 5 6] 2 3) let saved=a
let column=a[[..] 1]
a[[..] 1]=[20 50]
a[0 [1..3)]=99
assert(a.data =? [1 99 99 4 50 6] and saved.data =? [1 2 3 4 5 6])
assert(column.data =? [2 5])
a[[..] 0]=a[[..] 2]
assert(a.data =? [99 99 99 6 50 6])
a[[0..0) [..]]=[]
let box=[matrix=a] let old=box
box.matrix[[..] 1]=0
assert(box.matrix.data =? [99 0 99 6 0 6] and old.matrix.data =? a.data)
return 42}''',
    'numeric-matrix-slice-ranks': '''main=()=>{
let a=reshape([0 1 2 3 4 5 6 7 8 9 10 11] 2 2 3)
let part=a[1 [..] [1..3)]
assert(part.shape =? [2 2] and part.data =? [7 8 10 11])
let remaining=a[[0..1) [..]]
assert(remaining.shape =? [1 2 3] and remaining.data =? [0 1 2 3 4 5])
a[1 [..] [1..3)]=[70 80 100 110]
assert(a.data =? [0 1 2 3 4 5 6 70 80 9 100 110])
let b=ones(2 2 2 2) b[1 [..] 0 [..]]=0.0
assert(b[1 [..] 0 [..]].shape =? [2 2] and sum(b) =? 12.0)
return 42}''',
    'numeric-matrix-slice-managed': '''main=()=>{
let a=reshape(["a" "b" "c" "d"] 2 2) let saved=a
let part=a[[..] 0] part[0]="new"
a[[..] 1]=a[[..] 0]
assert(a.data =? ["a" "a" "c" "c"] and saved.data =? ["a" "b" "c" "d"])
assert(part.data =? ["new" "c"])
return 42}''',
    'numeric-matrix-slice-evaluation': '''let calls=""
source=()=>{calls+="s" return reshape([1 2 3 4 5 6] 2 3)}
first=()=>{calls+="a" return 0}
stop=()=>{calls+="b" return 2}
column=()=>{calls+="c" return 1}
replacement=()=>{calls+="v" return [20 50]}
main=()=>{
let part=source()[[first()..stop()) column()]
assert(calls =? "sabc" and part.data =? [2 5])
let a=source() calls=""
a[[first()..stop()) column()]=replacement()
assert(calls =? "abcv" and a.data =? [1 20 3 4 50 6])
return 42}''',
    'numeric-range-bracket-constructors': '''Pair:type=[a:IntRange b:IntRange]
Single:type=[range:IntRange]
main=()=>{
let pair=Pair[[0..2] (2..4]]
assert([loop i in pair.a i] =? [0 1 2])
assert([loop i in pair.b i] =? [3 4])
let stepped=Pair[[0,2..4] [4,2..0]]
assert([loop i in stepped.a i] =? [0 2 4] and [loop i in stepped.b i] =? [4 2 0])
let single=Single[0..2]
assert([loop i in single.range i] =? [0 1 2])
return 42}''',
    'numeric-matrix-copy': '''main=()=>{
let a=reshape([3.0 1.0 1.0 2.0] 2 2) let saved=a
let flat=flatten(a) let reshaped=reshape(a 1 4)
a[0 1]=4.0 flat[0]=99.0 reshaped[0 3]=7.0
assert(saved.data =? [3.0 1.0 1.0 2.0])
assert(a[0 1] =? 4.0 and a[0 0] =? 3.0 and a[1 1] =? 2.0)
return 42}''',
    'numeric-matrix-product': '''main=()=>{
let a=reshape([1 2 3 4 5 6] 2 3) let b=reshape([7 8 9 10 11 12] 3 2)
let c=a*b
assert(c.shape =? [2 2] and c.data =? [58 64 139 154])
assert(a*[2 3 4] =? [20 47])
let t=transpose(a)
assert(t.shape =? [3 2] and t.data =? [1 4 2 5 3 6])
assert(row(a 1) =? [4 5 6] and col(a 1) =? [2 5])
return 42}''',
    'numeric-matrix-solve': '''main=()=>{
let a=reshape([0.0 2.0 1.0 3.0] 2 2) let b=[4.0 7.0]
let x=solve(a b)
assert(abs(x[0]-1.0) <? 1e-12 and abs(x[1]-2.0) <? 1e-12)
let identity=a*inverse(a)
loop i in [0..2) {loop j in [0..2) {
assert(abs(identity[i j]-(if i =? j 1.0 else 0.0)) <? 1e-12)}}
assert(abs(det(a)+2.0) <? 1e-12)
assert(a.data =? [0.0 2.0 1.0 3.0] and b =? [4.0 7.0])
return 42}''',
    'numeric-matrix-ranks': '''main=()=>{
let a=zeros<int64>(2 3 4) a[1 2 3]=42
let b=ones(2 2 2 2) b[1 0 1 0]=9.0
let saved=b b[1 0 1 0]=7.0
assert(a.shape =? [2 3 4] and a[1 2 3] =? 42 and sum(a) =? 42)
assert(saved[1 0 1 0] =? 9.0 and b[0 0 0 0] =? 1.0)
let t=transpose(a)
assert(t.shape =? [4 3 2] and t[3 2 1] =? 42)
return 42}''',
    'numeric-matrix-empty': '''main=()=>{
let a=zeros(2 0) let b=zeros(0 3) let c=a*b
assert(c.shape =? [2 3] and c.data =? [0.0 0.0 0.0 0.0 0.0 0.0])
assert(transpose(a).shape =? [0 2] and size(transpose(a)) =? 0)
let huge=zeros(1<<32 0 1<<32)
assert(size(huge) =? 0 and huge.shape =? [1<<32 0 1<<32])
assert(size(ones(0 2)) =? 0 and size(rand(2 0)) =? 0 and size(randn(0 2)) =? 0)
assert(fill(0 -1).length =? 0)
return 42}''',
    'numeric-matrix-constructors': '''main=()=>{
let a=ones(2 3) let b=eye(3) let c=zeros<int64>(2 2)
assert(sum(a) =? 6.0 and mean(a) =? 1.0 and trace(b) =? 3.0)
assert((a+a).data =? [2.0 2.0 2.0 2.0 2.0 2.0])
assert((a*2.0).data =? (a+a).data and c.data =? [0 0 0 0])
let r=rand(2 3 4) let n=randn(2 2 2 2)
assert(r.shape =? [2 3 4] and size(r) =? 24 and size(n) =? 16)
loop x in r.data {assert(x >=? 0.0 and x <? 1.0)}
return 42}''',
    'numeric-sum-literal-integer': 'main=()=>sum([20 22])',
    'numeric-sum-literal-exact': '''main=()=>{
let result=sum([9007199254740993 1])
let wide=sum([18446744073709551614 1])
return if result=?9007199254740994 and wide=?18446744073709551615 42 else 1}''',
    'numeric-array-unsigned-inference': '''first=<T>(values:array<T>)=>values[0]
main=()=>{
let a=[18446744073709551615 1] let b=[1 18446744073709551615]
return if a[0]=?b[1] and first([18446744073709551615 0])=?18446744073709551615 42 else 1}''',
    'numeric-sum-literal-bigint': '''main=()=>if sum([18446744073709551616 1])=?18446744073709551617 42 else 1''',
    'numeric-sum-mixed-integer-elements': '''let calls=0
next=():>int64=>{calls+=1 return 9007199254740993}
main=()=>{
let value=next()
let a=sum([value 1]) let b=sum([1 value])
let c=sum([next() 1]) let d=sum([1 next()])
return if a=?9007199254740994 and b=?a and c=?a and d=?a and calls=?3 42 else 1}''',
    'generic-array-literal-float-overload': '''choose=<T>(values:array<T>)=>42
choose=(values:array<float64>)=>1
main=()=>choose([20 22])''',
    'generic-array-literal-nested-overload': '''choose=<T>(values:array<array<T>>)=>42
choose=(values:array<array<float64>>)=>1
main=()=>choose([[20 22]])''',
    'generic-array-literal-concrete-overload': '''choose=<T>(values:array<T>)=>1
choose=(values:array<uint8>)=>42
main=()=>choose([20 22])''',
    'generic-array-literal-bound-scalar-overload': '''choose=<T>(tag:T values:T)=>1
choose=<T>(tag:T values:array<T>)=>42
main=()=>{let tag:uint8=0
return if choose(tag [1 2 3 4])=?42 and choose<uint8>(0 [5 6 7 8])=?42 42 else 1}''',
    'generic-array-literal-length-independent': '''choose=<T>(value:T)=>1
choose=<T>(value:array<T>)=>42
main=()=>if choose([1])=?42 and choose([1 2])=?42 and choose([1 2 3])=?42
and choose([1 2 3 4])=?42 and choose([1 2 3 4 5 6 7 8])=?42 42 else 1''',
    'generic-array-literal-length-nested': '''choose=<T>(value:T)=>1
choose=<T>(value:array<array<T>>)=>42
main=()=>choose([[1 2 3 4] [5 6 7 8] [9 10 11 12]])''',
    'generic-array-literal-length-typed': '''choose=<T>(value:T)=>1
choose=<T>(value:array<T>)=>42
main=()=>{let x=1
return if choose([x 2 3 4])=?42 and choose([1 2 3 x])=?42 42 else 1}''',
    'generic-array-literal-length-narrow': '''choose=<T>(value:T)=>1
choose=(value:array<uint8>)=>42
main=()=>choose([1 2 3 4 5 6])''',
    'generic-array-literal-length-floating': '''choose=<T>(value:T)=>1
choose=(value:array<float64>)=>42
main=()=>choose([1 2 3 4 5 6])''',
    'generic-array-literal-deferred-float': '''choose=<T>(value:array<T>)=>1
choose=(value:array<float64>)=>42
main=()=>{let values=[1.0 2.0 3.0]
return if choose([20 values...])=?42 and choose([values... 20])=?42 42 else 1}''',
    'generic-array-literal-deferred-overflow': '''choose=<T>(value:array<T>)=>1
choose=(value:array<int64>)=>42
main=()=>{let narrow:int32=1
return if choose([2147483648 narrow])=?42 and choose([narrow 2147483648])=?42 42 else 1}''',
    'generic-array-literal-float-specific': '''choose=<T>(values:array<T>)=>1
choose=(values:array<float64>)=>42
main=()=>choose([20.0 22.0])''',
    'generic-array-mixed-float-specific': '''choose=<T>(values:array<T>)=>1
choose=(values:array<float64>)=>42
main=()=>{let floating=20.0 let integer=22
return if choose([floating 22])=?42 and choose([22 floating])=?42
and choose([integer 20.0])=?42 and choose([20.0 integer])=?42 42 else 1}''',
    'generic-array-literal-empty-specific': '''choose=<T>(values:array<T>)=>1
choose=(values:array<int64>)=>42
main=()=>choose([])''',
    'generic-array-literal-user-sum': '''sum=<T>(values:array<T>)=>17
main=()=>sum([20 22])+25''',
    'numeric-bounded-remainder': '''probe=(bytes:array<uint8>):>int64=>{
let word:int64=0
loop round in [0..50) {loop byte in bytes {word=(word*131+(byte as int64))%1000000007}}
return word}
main=()=>if probe([0 127 128 255 1])=?612902960 42 else 1''',
    'numeric-bounded-remainder-overflow': '''product=(byte:uint8):>int64=>{
let word:int64=9223372036854775807
word=(word*131+(byte as int64))%1000000007 return word}
sum=(byte:uint8):>int64=>{
let word:int64=9223372036854775607
word=(word+(byte as int64))%1000000007 return word}
narrow=(byte:int8):>int64=>(byte as int64)*131+255
main=()=>{
if product(255) not=?708828127 or sum(255) not=?708828057 return 1
if narrow(-128)%1000000007 not=?999983494 return 2
let high:uint64=18446744073709551615
return if ((high as int64)*131+255)%1000000007=?124 42 else 3}''',
    'numeric-bounded-remainder-writes': '''branch=(negative:bool):>int64=>{
let word:int64=0 if negative {word=-5}
word=(word*131+255)%1000000007 return word}
compound=():>int64=>{
let word:int64=0 word-=5
word=(word*131+255)%1000000007 return word}
tuple_write=():>int64=>{
let word:int64=0 let other:int64=0
[word other]=[-5 42]
word=(word*131+255)%1000000007 return word+other}
main=()=>if branch(true)=?999999607 and branch(false)=?255
and compound()=?999999607 and tuple_write()=?999999649 42 else 1''',
    'numeric-bounded-remainder-escape': '''change=(@value:int64):>void=>{value=-5}
reference=():>int64=>{
let word:int64=0 change(@word)
word=(word*131+255)%1000000007 return word}
closure=():>int64=>{
let word:int64=0 let mutate=($capture @word)=>{word=-5} mutate()
word=(word*131+255)%1000000007 return word}
main=()=>if reference()=?999999607 and closure()=?999999607 42 else 1''',
    'numeric-bounded-remainder-once': '''let calls:int64=0
byte=():>uint8=>{calls+=1 return 255}
main=()=>{
let word:int64=0 loop i in [0..20) {word=(word*131+(byte() as int64))%1000000007}
return if calls=?20 and word>=?0 42 else 1}''',
    'numeric-constant-floor-once': '''let calls:int64=0
next=():>int64=>{calls+=1 return -7}
main=()=>{
let values=[next()%3 next()//3 next()%1 next()//1 next()%2 next()//2 next()%8 next()//8]
return if calls=?8 and values=?[2 -3 0 -7 1 -4 1 -1] 42 else 1}''',
    'numeric-floor-helper-overloads': ('import p"'+(Path(__file__).resolve().parents[2] / 'core/tests/floor_helpers.jo').as_posix()+'"\n'
                                       'main=()=>floor_helpers.check()'),
    'array-comparison-word-boundaries': '''verify=<T>(values:array<T> different:T):>bool=>{
loop count in [0..values.length] {
let a=values[0..count) let b=values[0..count) let shared=a
if a not=?b or a not=?shared return false
loop index in [0..count) {
let changed=b changed[index]=different
if a=?changed or changed=?a return false
}
if count <? values.length and a=?values return false
}
return true
}
main=()=>{
let bytes:array<uint8>=[0 1 127 128 254 0 1 127 128 254 0 1 127 128 254 0 1]
let signed:array<int8>=[-128 -1 0 1 126 -128 -1 0 1 126 -128 -1 0 1 126 0 1]
let words:array<uint16>=[0 1 255 256 65534 0 1 255 256]
let ints:array<int32>=[-2147483648 -1 0 1 2147483646]
let wide:array<uint64>=[0 1 9223372036854775808 18446744073709551614]
return if verify(bytes 255) and verify(signed 127) and verify(words 65535)
and verify(ints 2147483647) and verify(wide 18446744073709551615) 42 else 1}''',
    'array-comparison-bool-snapshots': '''main=()=>{
let values=[true false true false true false true false true]
let saved=values let equal=[true false true false true false true false true]
if values not=?equal or values not=?saved return 1
loop index in [0..values.length) {
let changed=values changed[index]=not changed[index]
if changed=?saved return 2
}
let empty:array<bool>=[] let reserved:array<bool>=[] reserved.reserve(16)
return if values=?saved and empty=?reserved 42 else 3}''',
    'array-comparison-nonreflexive': '''Key:type=[value:int64]
let calls:int64=0
__eq__=(a:Key b:Key):>bool=>{calls+=1 return false}
main=()=>{
let zero:float64=0.0 let nan=zero/zero let values=[nan] let shared=values
if values=?shared return 1
if [0.0] not=?[-0.0] return 2
let keys=[Key[42]] let copy=keys
return if keys not=?copy and calls=?1 42 else 3}''',
    'sequence-value-protocol-demand': '''Box:type=<T>[value:T]
__eq__=<T>(a:Box<T> b:Box<T>):>bool=>a.value=?b.value
hash=<T>(box:Box<T>):>uint64=>box.value.special_hash()
HashOnly:type=<T>[value:T]
__eq__=<T>(a:HashOnly<T> b:HashOnly<T>):>bool=>a.value.special_equal(b.value)
hash=<T>(box:HashOnly<T>):>uint64=>(box.value as uint64).hash()
main=()=>{
if [Box<int64>[20]] not=?[Box<int64>[20]] return 1
return if hash([HashOnly<int64>[22]])=?hash([HashOnly<int64>[22]]) 42 else 2}''',
    'sequence-value-protocol-nesting': ('from p"'+(Path(__file__).resolve().parents[2] / 'core/tests/hash_keys.dewy').as_posix()+'" import Key, Tagged\n'+'''main=()=>{
let a=Key[7 "first"] let b=Key[7 "other"]
if [a] not=?[b] or [item=a] not=?[item=b] return 1
let optional:Key?=a let other:Key?=b
if optional not=?other return 2
let variant:Key|string=a let second:Key|string=b
if variant not=?second return 3
if hash([a]) not=?hash([b]) or hash([item=a]) not=?hash([item=b]) return 4
let keys=[[item=[a]]->42]
if keys[[item=[b]]] not=?42 return 5
let generic=[Tagged<string>["same" "first"]]
return if generic=?[Tagged<string>["same" "other"]] 42 else 6}'''),
    'sequence-value-protocol-outer-override': '''Inner:type=[value:int64]
Outer:type=[id:int64 ignored:Inner]
__eq__=(a:Inner b:Inner):>bool=>false
__eq__=(a:Outer b:Outer):>bool=>a.id=?b.id
hash=(value:Outer):>uint64=>(value.id as uint64).hash()
main=()=>{
let a=Outer[7 Inner[20]] let b=Outer[7 Inner[22]]
let values=[a->42]
return if [a]=?[b] and hash([a])=?hash([b]) values[b] else 1}''',
    'sequence-value-protocol-equality-snapshot': '''Key:type=[value:int64]
let current:array<Key>=[] let armed=false let calls:int64=0
__eq__=(a:Key b:Key):>bool=>{
calls+=1
if armed {armed=false current.clear()}
return a.value=?b.value
}
through=(values:array<Key>):>int64=>{
if values not=?[Key[20] Key[22]] return 1
let noise=[Key[99] Key[100]]
return if noise.length=?2 values[0].value+values[1].value else 2
}
main=()=>{
current=[Key[20] Key[22]] armed=true
let result=through(current)
return if current.length=?0 and calls=?2 result else 3}''',
    'sequence-value-protocol-hash-snapshot': '''Key:type=[value:int64]
let current:array<Key>=[] let armed=false let calls:int64=0
hash=(key:Key):>uint32=>{
calls+=1
if armed {armed=false current.clear()}
return key.value as uint32
}
through=(values:array<Key>):>int64=>{
let code=hash(values)
let noise=[Key[99] Key[100]]
return if noise.length=?2 and code=?hash([Key[20] Key[22]])
values[0].value+values[1].value else 1
}
main=()=>{
current=[Key[20] Key[22]] armed=true
let result=through(current)
return if current.length=?0 and calls=?4 result else 2}''',
    'generic-instance-identity': '''A:type=[value:int64]
B:type=[value:int64]
identity=<T>(value:T):>T=>value
first=<T U>(a:T b:U):>T=>a
second=<T U>(a:T b:U):>U=>b
score=(value:A):>int64=>value.value
score=(value:B):>int64=>value.value+1
main=()=>{
let a=identity(A[20]) let b=identity(B[21])
let copied=identity([a.value b.value]) copied[0]=99
if first<int64 string>(20 "ignored") not=?20 return 1
if second<int64 string>(20 "kept") not=?"kept" return 2
if first<string int64>("kept" 22) not=?"kept" return 3
return score(identity(a))+score(identity(b))}''',
    'generic-instance-recursion': '''recur_value=<T>(value:T depth:int64):>T=>
if depth=?0 value else recur_value(value depth-1)
main=()=>{
let values=[20 22]
let copied=recur_value(values 5) copied[0]=99
return if recur_value("kept" 2)=?"kept" and recur_value(true 3)
values[0]+recur_value(values[1] 4) else 1}''',
    'dictionary-optional-payload': '''main=()=>{
let values:dict<int64 int64?>=[1->none 2->42]
if values.get(1) is? none or values.get(3) isnt? none return 1
if values.get(1) =? none or values.get(3) not=? none return 2
let empty=values.get(1) let present=values.get(2) let missing=values.get(3)
if empty is? none or present is? none or missing isnt? none return 3
let inner_empty=empty let inner_present=present
if inner_empty isnt? none or inner_present is? none return 4
return inner_present}''',
    'dictionary-optional-managed-payload': '''main=()=>{
let values:dict<int64 array<int64>?>=[1->none 2->[20 22]]
let found=values.get(2) let empty=values.get(1)
if found is? none or empty is? none return 1
let inner=found let absent=empty
if inner is? none or absent isnt? none return 2
let saved=inner
inner[0]=99 values.clear()
return saved[0]+saved[1]}''',
    'generic-optional-wrapper': '''Optional:type=int64?
wrap=<T>(value:T):>T?=>value
read=(value:Optional?):>int64=>{
if value is? none return 1
let inner=value
if inner is? none return 20
return inner
}
main=()=>{
let empty:Optional=none let value:Optional=22
let wrapped:Optional?=empty
return if read(wrapped)=?20 and read(none)=?1
read(wrap<Optional>(empty))+read(wrap<Optional>(value)) else 2}''',
    'dictionary-presence-forms': '''main=()=>{
let values=[1->0 2->42]
if values.get(1) is? none or values.get(3) isnt? none return 1
if values.get(1) =? none or values.get(3) not=? none return 2
if none =? values.get(2) or none not=? values.get(3) return 3
if not (values.get(2) is? int64) return 4
let flags=[1->false]
if flags.get(1) is? none return 5
let managed=[1->[20 22]]
if managed.get(1) is? none or managed.get(2) isnt? none return 6
return values.get(2)??0}''',
    'dictionary-presence-default-values': '''main=()=>{
let values:dict<int64 int64?>=[1->none 2->42]
if values.get(1 none) isnt? none or values.get(3 none) isnt? none return 3
if values.get(3 42) is? none return 4
return 42}''',
    'dictionary-presence-argument-order': '''let trace:int64=0
let values:dict<int64 array<int64>>=[1->[42]]
source=():>dict<int64 array<int64>>=>{trace=trace*10+1 return values}
key=():>int64=>{trace=trace*10+2 values.clear() return 1}
main=()=>{
if source().get(key()) is? none or trace not=?12 return 1
values=[1->[42]] trace=0
if get(k=key() m=source()) isnt? none or trace not=?21 return 2
values=[1->[42]] trace=0
if none =? source().get(key()) or trace not=?12 return 3
return 42}''',
    'dictionary-presence-custom-methods': '''Box:type=[value:int64?]
get=(box:Box key:int64):>int64?=>box.value
has=(box:Box key:int64):>bool=>false
has=(values:dict<int64 int64> key:int64):>bool=>false
main=()=>{
let box=Box[42] let empty=Box[none]
if box.get(1) is? none or box.get(1) =? none return 1
if empty.get(1) isnt? none or empty.get(1) not=? none return 2
let values=[1->42]
if values.get(1) is? none or values.get(1) =? none return 3
return 42}''',
    'dictionary-presence-callback-snapshot': '''Key:type=[value:int64]
let values:dict<Key array<int64>>=[]
let hash_calls:int64=0 let equal_calls:int64=0 let armed=false
hash=(key:Key):>uint64=>{
hash_calls+=1
if armed values.clear()
return 0
}
__eq__=(a:Key b:Key):>bool=>{
equal_calls+=1
if armed values.clear()
return a.value =? b.value
}
main=()=>{
values=[Key[1]->[42]] hash_calls=0 equal_calls=0 armed=true
if values.get(Key[1]) is? none return 1
if values.length not=?0 or hash_calls not=?1 or equal_calls not=?1 return 2
armed=false values=[Key[1]->[42]] hash_calls=0 equal_calls=0 armed=true
if values.get(Key[2]) not=? none return 3
return if values.length=?0 and hash_calls=?1 and equal_calls=?1 42 else 4}''',
    'sequence-mutable-scalars': """main=()=>{
let values=[20 21] let saved=values
loop @value in values {value+=1}
if values not=?[21 22] or saved not=?[20 21] return 1
loop value in values {let copy=value copy=0}
return if values=?[21 22] 42 else 2}""",
    'sequence-mutable-managed': """Item:type=[count:int64 parts:array<int64>]
bump=(@item:Item):>void=>{item.count+=1 item.parts.push(22)}
main=()=>{
let items=[Item[19 [20]] Item[21 [20]]] let saved=items
loop @item in items {bump(@item) item.parts[0]+=1}
return if items[0].count=?20 and items[1].count=?22
and items[0].parts=?[21 22] and items[1].parts=?[21 22]
and saved[0].count=?19 and saved[0].parts=?[20] 42 else 1}""",
    'sequence-mutable-fields-fixed': """Box:type=[items:array<array<int64> length=2>]
Outer:type=[box:Box]
update=(@outer:Outer):>void=>{loop @row in outer.box.items row.push(22)}
main=()=>{
let outer=Outer[Box[[[20] [21]]]] let saved=outer
update(@outer)
return if outer.box.items[0]=?[20 22] and outer.box.items[1]=?[21 22]
and saved.box.items[0]=?[20] and saved.box.items[1]=?[21] 42 else 1}""",
    'sequence-mutable-snapshot-in-body': """main=()=>{
let values=[[20] [21]] let snapshots:array<array<array<int64>>>=[]
loop @value in values {snapshots.push(values) value[0]+=1 value.push(22)}
return if values=?[[21 22] [22 22]]
and snapshots[0]=?[[20] [21]] and snapshots[1]=?[[21 22] [21]] 42 else 1}""",
    'sequence-mutable-nested': """main=()=>{
let rows=[[19 20] [21 22]] let saved=rows
loop @row in rows {loop @value in row value+=1}
return if rows=?[[20 21] [22 23]] and saved=?[[19 20] [21 22]] 42 else 1}""",
    'sequence-mutable-closure-snapshots': """main=()=>{
let values=[[20] [22]] let readers:array<(():>array<int64>)>=[]
loop @value in values {let captured=value readers.push(()=>captured) value[0]=99}
return if readers[0]()=?[20] and readers[1]()=?[22] and values=?[[99] [99]] 42 else 1}""",
    'sequence-mutable-control': """main=()=>{
let values=[0 1 2 3] let empty:array<int64>=[] let total=0
loop @value in empty {return 1} else {total+=10}
loop @value in values {
value+=10
if value=?10 continue
if value=?12 break
} else {return 2}
$outer
loop @value in values {
loop i in [0..2) {value+=1 continue $outer}
} else {return 3}
return if total=?10 and values=?[11 12 13 4] 42 else 4}""",
    'sequence-mutable-comprehension': """main=()=>{
let values=[19 21] let saved=values
let doubled=[loop @value in values {value+=1; value*2}]
let empty:array<int64>=[]
let fallback=[loop @value in empty value else 42]
return if values=?[20 22] and saved=?[19 21]
and doubled=?[40 44] and fallback=?[42] 42 else 1}""",
    'sequence-mutable-replace-element': """Item:type=[parts:array<int64>]
main=()=>{let values=[Item[[1]] Item[[2]]] let saved=values
loop @item in values {let old=item item=Item[[20 22]] old.parts[0]=99}
return if values[0].parts=?[20 22] and values[1].parts=?[20 22]
and saved[0].parts=?[1] and saved[1].parts=?[2] 42 else 1}""",
    'sequence-mutable-value-parameter': """update=(values:array<int64>):>array<int64>=>{
loop @value in values value+=1
return values
}
main=()=>{let values=[19 21] let result=update(values)
return if result=?[20 22] and values=?[19 21] 42 else 1}""",
    'sequence-mutable-return-cleanup': """first=(@values:array<array<int64>>):>array<int64>=>{
loop @value in values {value.push(22) return value}
return []
}
main=()=>{
let values=[[20] [99]] let saved=values let result=first(@values)
values[0][0]=0
return if result=?[20 22] and saved=?[[20] [99]] and values=?[[0 22] [99]] 42 else 1}""",
    'sequence-slice-loop-bound-locals': '''main=()=>{
let values=[99 20 22 100] let start:int64=1
let chosen=values[start..({start=0; 3}))
if chosen not=?[20 22] or start not=?0 return 1
start=1 let sum:int64=0
loop value in values[start..({start=0; 3})) sum+=value
return if start=?0 sum else 2}''',
    'sequence-slice-loop-replaced-by-bound': '''let values:array<int64>=[99 20 22 100]
let trace:int64=0
lower=():>int64=>{trace=trace*10+2 values=[99] return 1}
upper=():>int64=>{trace=trace*10+3 return 3}
main=()=>{
let sum:int64=0
loop value in values[lower()..upper()) {trace=trace*10+4 sum+=value}
return if trace=?2344 and values=?[99] sum else 1}''',
    'sequence-slice-loop-no-allocation': '''main=()=>{
let values=[99 20 22 100]
let before=alloc_count() let sum:int64=0
loop value in values[1..3) {
if alloc_count() not=?before return 1
sum+=value
}
return if alloc_count()=?before sum else 2}''',
    'sequence-slice-loop-bounds-order': '''let values:array<int64>=[99 20 22 100]
let trace:int64=0
source=():>array<int64>=>{trace=trace*10+1 return values}
lower=():>int64=>{trace=trace*10+2 values=[99] return 1}
upper=():>int64=>{trace=trace*10+3 return 3}
main=()=>{
let sum:int64=0
loop value in source()[lower()..upper()) {trace=trace*10+4 sum+=value}
return if trace=?12344 and values=?[99] sum else 1}''',
    'sequence-slice-loop-snapshots': '''main=()=>{
let values=[[99] [20] [22] [100]] let saved=values
let sum:int64=0
loop item in values[1..2] {
values.clear() values.push([1])
let copy=item copy[0]=99
sum+=item[0]
}
return if saved[1]=?[20] and saved[2]=?[22] sum else 1}''',
    'sequence-slice-loop-control': '''first=(values:array<int64>):>int64=>{
loop value in values[1..] return value
return 0
}
main=()=>{
let values=[99 20 22 100] let before=alloc_count()
let sum=first(values)
loop value in values[2..] {sum+=value break}
loop value in values[0..0) return 1
let visited=[loop value in values[1..3) value]
let empty=first([99])
return if visited=?[20 22] and empty=?0
and alloc_count()=?before+1 sum else 2}''',
    'sequence-minmax-by-order': '''let trace:int64=0
key=(value:int64):>int64=>{trace=trace*10+value return value}
main=()=>{
let values=[4 2 8 1]
if values.min_by(key) not=?1 or trace not=?4281 return 1
trace=0
if values.max_by(key) not=?8 or trace not=?4281 return 2
trace=0
return if [42].min_by(key)=?42 and trace=?42 42 else 3}''',
    'sequence-minmax-by-ties-and-copies': '''Item:type=[rank:int64 values:array<int64>]
key=(item:Item):>int64=>item.rank
main=()=>{
let items=[Item[1 [20]] Item[1 [99]] Item[2 [22]] Item[2 [100]]]
let low=items.min_by(key) let high=items.max_by(key)
let saved=low low.values[0]=0 high.values[0]=0
return if items[0].values[0]=?20 and items[2].values[0]=?22
and saved.values[0]=?20 saved.values[0]+items[2].values[0] else 1}''',
    'sequence-minmax-by-custom-order': '''Rank:type=[value:int64]
__lt__=(a:Rank b:Rank):>bool=>a.value <? b.value
key=(value:int64):>Rank=>Rank[-value]
main=()=>[20 22].min_by(key)+[20 22].max_by(key)''',
    'sequence-minmax-by-source-mutation': '''let source:array<int64>=[20 22]
let calls:int64=0
key=(value:int64):>int64=>{calls+=1 source=[99] return value}
main=()=>{
let low=source.min_by(key)
if low not=?20 or calls not=?2 or source not=?[99] return 1
source=[20 22] calls=0
let high=source.max_by(key)
return if high=?22 and calls=?2 and source=?[99] low+high else 2}''',
    'sequence-minmax-by-no-tail-allocation': '''let before:int64=0
let extra=false
key=(value:int64):>int64=>{if alloc_count() not=?before extra=true return value}
main=()=>{
let values=[20 99 22 1]
values.min_by(key) values.max_by(key)
before=alloc_count() extra=false
let low=values.min_by(key) let high=values.max_by(key)
return if not extra and low=?1 and high=?99 42 else 1}''',
    'dictionary-equality-callback-borrow': ('import p"'+(Path(__file__).resolve().parents[2] / 'core/tests/set_effects.jo').as_posix()+'"\n'+'''through=(values:array<dict<int64 set_effects.Key>>):>int64=>{
let other=[[2->set_effects.Key[22] 1->set_effects.Key[20]]]
if values not=?other return 1
let noise=[[3->set_effects.Key[99]]]
return if noise.length=?1 values[0].length*21 else 2
}
main=()=>{
set_effects.current_maps=[[1->set_effects.Key[20] 2->set_effects.Key[22]]]
set_effects.armed=true
let result=through(set_effects.current_maps)
return if set_effects.current_maps.length=?0 and not set_effects.armed result else 3}'''),
    'dictionary-hash-callback-borrow': ('import p"'+(Path(__file__).resolve().parents[2] / 'core/tests/hash_keys.dewy').as_posix()+'"\n'+'''through=(values:array<dict<int64 hash_keys.Key>>):>int64=>{
let code=hash(values)
let noise=[[3->hash_keys.Key[99 "other"]]]
return if noise.length=?1 and code=?hash(values) values[0].length*21 else 1
}
main=()=>{
hash_keys.current_maps=[[1->hash_keys.Key[20 "a"] 2->hash_keys.Key[22 "b"]]]
hash_keys.armed=true
let result=through(hash_keys.current_maps)
return if hash_keys.current_maps.length=?0 and not hash_keys.armed result else 2}'''),
    'dictionary-value-equality': '''main=()=>{
let first=["a"->[20] "b"->[22]]
let second=["b"->[22] "gone"->[0] "a"->[20]]
second.remove("gone") second.reserve(100)
if first not=?second or [first] not=?[second] return 1
if [mapping=first] not=?[mapping=second] return 2
let optional:dict<string array<int64>>?=first
if optional not=?second return 3
let variant:dict<string array<int64>>|string=first
let other:dict<string array<int64>>|string=second
if variant not=?other return 4
let values=[first->42]
let saved=second second["a"].push(99)
return if second not in? values values[saved] else 5}''',
    'dictionary-empty-hash': '''main=()=>{
let first:dict<int64 string>=[] let second:dict<int64 string>=[]
second.reserve(100) second[7]="gone" second.remove(7)
let values=set[first second]
return if values.length=?1 and [first]=?[second] 42 else 1}''',
    'dictionary-custom-nested-hash': ('from p"'+(Path(__file__).resolve().parents[2] / 'core/tests/hash_keys.dewy').as_posix()+'" import Key\n'+'''main=()=>{
let first=[Key[20 "a"]->Key[22 "b"]]
let second=[Key[20 "other"]->Key[22 "labels"]]
let values=[[mapping=first]->42]
return values[[mapping=second]]}'''),
    'dictionary-custom-hash': ('from p"'+(Path(__file__).resolve().parents[2] / 'core/tests/hash_keys.dewy').as_posix()+'" import Key\n'+'''main=()=>{
let values:dict<Key int64>=[]
values[Key[7 "first"]]=20
values[Key[7 "second"]]+=22
if values.length not=?1 or not values.has(Key[7 "third"]) return 1
if values.get(Key[7 "fourth"]) not=?42 return 2
if values.insert_if_absent(Key[7 "fifth"] 99) return 3
let saved=values
if not values.remove(Key[7 "sixth"]) or values.length not=?0 return 4
return saved[Key[7 "last"]]}'''),
    'set-custom-hash': ('from p"'+(Path(__file__).resolve().parents[2] / 'core/tests/hash_keys.dewy').as_posix()+'" import Key, Tagged\n'+'''main=()=>{
let first=set[Key[20 "a"] Key[22 "b"] Key[20 "c"]]
let second=set[Key[22 "other"] Key[20 "labels"]]
if first.length not=?2 or first not=?second return 1
let outer=set[first second]
if outer.length not=?1 or second not in? outer return 2
let records=[[members=first]->42]
if records[[members=second]] not=?42 return 3
let generic=set[Tagged<string>["same" "a"] Tagged<string>["same" "b"]]
return if generic.length=?1 42 else 4}'''),
    'set-hash-callback-borrow': ('import p"'+(Path(__file__).resolve().parents[2] / 'core/tests/hash_keys.dewy').as_posix()+'"\n'+'''through=(values:array<set<hash_keys.Key>>):>int64=>{
let code=hash(values)
let noise=[set[hash_keys.Key[99 "other"]]]
return if noise.length=?1 and code=?hash(values) values[0].length*21 else 1
}
main=()=>{
hash_keys.current=[set[hash_keys.Key[20 "a"] hash_keys.Key[22 "b"]]]
hash_keys.armed=true
let result=through(hash_keys.current)
return if hash_keys.current.length=?0 and not hash_keys.armed result else 2}'''),
    'set-membership': '''main=()=>{
let seen=set["read" "write" "read"]
seen.push("execute") seen.push("write")
if seen.length not=? 3 or "read" not in? seen or "absent" in? seen return 1
if seen.add("read") or not seen.add("new") return 2
return if seen.has("new") and seen.contains("write") and not seen.is_empty() 42 else 3}''',
    'set-typed-literals': '''sum=(values:set<int8>):>int64=>{
let result:int64=0 loop value in values {result+=value as int64} return result}
empty=():>set<uint64>=>set[]
wrap=<T>(value:T):>set<T>=>set[value]
main=()=>{
let values:set<uint8>=set[20 22 20]
let absent:set<string>?=set[]
let high:uint64=uint64.max
if empty().length not=? 0 or absent is? none or absent.length not=? 0 return 1
if high not in? wrap(high) or values.length not=? 2 return 2
return sum(set[20 22])}''',
    'set-algebra': '''main=()=>{
let evens=set[0 2 4 6 8] let small=set[0 1 2 3]
if [loop x in (evens & small) x] not=? [0 2] return 1
if [loop x in (evens | small) x] not=? [0 2 4 6 8 1 3] return 2
if [loop x in (evens-small) x] not=? [4 6 8] return 3
if [loop x in (evens xor small) x] not=? [4 6 8 1 3] return 4
if evens not=? set[8 6 4 2 0] or small =? evens return 5
return if (evens & evens)=?evens and (evens-evens).length=?0 42 else 6}''',
    'set-copy-and-removal': '''main=()=>{
let values=set[20 99 22] let before=values
if not values.remove(99) or values.remove(99) return 1
values.push(20) values.reserve(100)
if [loop v in values v] not=? [20 22] or before.length not=? 3 return 2
let saved=values values.clear()
return if values.is_empty() and saved.length=?2 and 99 in? before 42 else 3}''',
    'set-pop': '''main=()=>{
let values=set[20 22]
let first=values.pop(20)
if values.pop(99 default=none) not=? none return 1
let second=values.pop(22 default=none)
if second is? none return 2
return if values.length=?0 first+second else 3}''',
    'set-iteration-snapshot': '''main=()=>{
let values=set[20 22] let trace:int64=0 let total:int64=0
loop i in 0.. and value in {trace+=1; values} {
total+=value values.remove(value) values.push(i)
}
if trace not=? 1 or [loop v in values v] not=? [0 1] return 1
let zipped=[loop a in set[20 22] and b in [1 2] a+b]
if zipped not=? [21 24] return 2
return total}''',
    'set-unpack': '''main=()=>{
let values=set[20 99 22] values.remove(99)
let [first second]=values
[second first]=set[first second]
return if first=?22 and second=?20 first+second else 1}''',
    'set-managed-keys': '''main=()=>{
let item=[20] let values=set[item [22] item] item[0]=99
let [first second]=values let saved=first first[0]=100
return if values.length=?2 and [20] in? values and [99] not in? values
and saved[0]=?20 saved[0]+second[0] else 1}''',
    'set-format': '''main=()=>{
let values=set[20 22 20]
return if "{values}"=?"set{[20 22]}" 42 else 1}''',
    'set-nested-hash': '''main=()=>{
let left=set[20 22] let right=set[22 99 20]
right.remove(99) right.reserve(100)
let values=set[left right]
let mapping=[left->42]
if values.length not=? 1 or right not in? values return 1
right.push(99)
return if right not in? values mapping[set[22 20]] else 2}''',
    'set-comprehension-and-generic': '''identity=(value)=>value
main=()=>{
let calls:int64=0
let values=identity(set[loop value in [20 22 20] {calls+=1; value}])
let output=[loop a in values or b in [1 2 3] a??0]
return if calls=?3 and output=?[20 22 0] 42 else 1}''',
    'set-literal-overload': '''pick=(values:set<int8>)=>1
pick=(values:set<int64>)=>42
main=()=>pick(set[20 22])''',
    'set-pop-any': '''main=()=>{
let values=set[20 99 22] values.remove(99)
let before=values let first=values.pop()
let second=values.pop(default=none)
if second is? none return 1
if values.pop(default=none) not=? none or before.length not=?2 return 2
return first+second}''',
    'set-pop-tail-constructor': '''main=()=>{
let values=set[20 99 22 20 22] values.remove(99)
if values.pop() not=? 22 or values.pop() not=? 20 return 1
values.push(42) values.reserve(100)
return if values.pop() =? 42 and values.pop(default=none) =? none 42 else 2}''',
    'set-pop-tail-compaction': '''main=()=>{
let values=set[loop i in [0..64) i]
loop i in [40..64) values.remove(i)
if values.pop() not=? 39 return 1
loop i in [0..30) values.remove(i)
if [values...] not=? [30 31 32 33 34 35 36 37 38] return 2
values.add(99) values.remove(99)
if values.pop() not=? 38 return 3
values.add(100) values.add(100)
if values.pop() not=? 100 return 4
loop expected in [37,36..30] {if values.pop() not=? expected return 5}
values.clear() values.push(42)
return values.pop()}''',
    'set-pop-tail-operation-trace': '''main=()=>{
let values:set<int64>=set[] let expected:array<int64>=[]
loop step in [0..1200) {
let key=(step*37+11)%41 let action=step%7
if action <? 3 {
let fresh=key not in? expected
if values.add(key) not=? fresh return 1
if fresh expected.push(key)
} else if action =? 3 {
if values.remove(key) not=? (key in? expected) return 2
loop i in [0..expected.length) {if expected[i] =? key {expected.remove(i) break}}
} else if action =? 4 {
if expected.length >? 0 {if values.pop() not=? expected.pop() return 3}
else {if values.pop(default=none) isnt? none return 4}
} else if action =? 5 {
let copy=values
if expected.length >? 0 {if copy.pop() not=? expected[end] return 5}
} else if step%13 =? 0 {values.clear() expected.clear()}
if [values...] not=? expected return 6
}
loop expected.length >? 0 {if values.pop() not=? expected.pop() return 7}
return if values.is_empty() 42 else 8}''',
    'set-pop-tail-managed-copies': '''main=()=>{
let values=set[[20] [99] [22]] values.remove([99])
let saved=values let item=values.pop()
item[0]=999
if [saved...] not=? [[20] [22]] or [values...] not=? [[20]] return 1
values.push([42])
if values.pop() not=? [42] or saved.pop() not=? [22] return 2
return values.pop()[0]+22}''',
    'set-pop-tail-cleanup': '''work=()=>{
let values=set[loop i in [0..100) [i i+1]]
loop i in [0,3..100) values.remove([i i+1])
let copy=values let total:int64=0
loop not values.is_empty() {let item=values.pop() total+=item[1]-item[0]}
loop not copy.is_empty() copy.pop()
return total
}
main=()=>{if work() not=? 66 return 1 let before=alloc_count()
loop i in [0..10) {if work() not=? 66 return 2}
return if alloc_count() =? before 42 else 3}''',
    'set-context-comparison': '''main=()=>{
let values:set<uint8>=set[20 22]
if values not=? set[20 22] or set[22 20] not=? values return 1
if (values | set[20 22 24]).length not=?3 return 2
if (set[20 22 24]-values) not=? set[24 as uint8] return 3
let optional:set<uint8>?=values
return if optional=?set[22 20] and set[20 22]=?optional 42 else 4}''',
    'set-spread-and-records': '''main=()=>{
let source:array<uint8>=[20 22]
let values:set<uint8>=set[source... 20]
source[0]=99
let records=set[[value=42] [value=0] [value=42]]
let [[value] _]=records
return if values=?set[20 22] and records.length=?2 value else 1}''',
    'set-spread-insertion-order': '''main=()=>{
let source=set[10 99 20 22] source.remove(99) source.add(10)
let values=[source... 42 source...]
source.remove(10) source.add(10)
return if values =? [10 20 22 42 10 20 22] and [source...] =? [20 22 10] 42 else 1}''',
    'set-spread-set-result': '''main=()=>{
let first=set[20 99 22] first.remove(99)
let second=set[first... 22 42 [20 1]...]
first.clear()
return if [second...] =? [20 22 42 1] and second.length =? 4 42 else 1}''',
    'set-spread-literal-context': '''sum=(items:array<uint16>)=>items[0]+items[1]
main=()=>{
let values:array<uint8>=[set[]... set[20 22]...]
let unique:set<uint8>=set[set[]... set[20 22]... 20]
let inferred=[set[]... 42]
return if values =? [20 22] and unique =? set[20 22] and inferred =? [42]
sum([set[20 22]...]) as int64 else 1}''',
    'set-spread-generic-overload': '''append=<T>(source:set<T> item:T):>array<T>=>[source... item]
choose=(values:array<uint8>)=>1
choose=(values:array<int64>)=>42
main=()=>{
let small:set<uint8>=set[20]
let words=append(set["first"] "last")
if append(small 22) not=? [20 as uint8 22 as uint8] return 1
if words not=? ["first" "last"] return 2
return choose([set[20 22]...])}''',
    'set-spread-order-snapshot': '''let source=set[20 21] let calls:int64=0
read=()=>{calls=calls*10+1 return source}
change=()=>{calls=calls*10+2 source.remove(20) source.add(22) return 42}
main=()=>{let values=[read()... change() source...]
return if calls =? 12 and values =? [20 21 42 21 22] 42 else 1}''',
    'set-spread-managed-copies': '''Item:type=[values:array<int64>]
main=()=>{
let source=set[Item[[20]] Item[[22]]]
let values=[source...]
values[0].values[0]=99
let unique=set[source... Item[[42]]]
source.clear()
return if [unique...] =? [Item[[20]] Item[[22]] Item[[42]]]
and values =? [Item[[99]] Item[[22]]] 42 else 1}''',
    'set-spread-extend': '''main=()=>{
let source:set<uint8>=set[20 22]
let values:array<uint8>=[]
values.extend(source) values.extend(set[]) values.extend(set[42])
source.clear()
return if values =? [20 22 42] values[end] as int64 else 1}''',
    'set-spread-cleanup': '''work=()=>{
let source=set[[20] [99] [22]] source.remove([99])
let values=[source...] let copied=set[source... [42]]
values[0][0]=0
return if [copied...] =? [[20] [22] [42]] 42 else 1
}
main=()=>{if work() not=? 42 return 1 let before=alloc_count()
loop i in [0..30) {if work() not=? 42 return 2}
return if alloc_count() =? before 42 else 3}''',
    'set-nested-value-equality': '''main=()=>{
let first=[tags=set[20 22] count=7]
let second=[tags=set[22 20] count=7]
if first not=? second or [first] not=? [second] return 1
let values=[first->42]
return values[second]}''',
    'set-union-value-equality': '''main=()=>{
let first:set<int64>|string=set[20 22]
let second:set<int64>|string=set[22 20]
if first not=? second return 1
let values=[first->42]
return values[second]}''',
    'set-equality-callback-snapshot': ('import p"'+(Path(__file__).resolve().parents[2] / 'core/tests/set_effects.jo').as_posix()+'"\n'+'''main=()=>{
set_effects.current=[set[set_effects.Key[20] set_effects.Key[22]]]
let other=[set[set_effects.Key[22] set_effects.Key[20]]]
set_effects.armed=true
if set_effects.current not=? other return 1
return if set_effects.current.length=?0 and not set_effects.armed 42 else 2}'''),
    'set-callback-borrowed-argument': ('import p"'+(Path(__file__).resolve().parents[2] / 'core/tests/set_effects.jo').as_posix()+'"\n'+'''through=(value:array<set<set_effects.Key>>):>int64=>{
let other=[set[set_effects.Key[22] set_effects.Key[20]]]
if value not=? other return 1
let noise=[set[set_effects.Key[99]]]
return if noise.length=?1 value[0].length*21 else 2
}
main=()=>{
set_effects.current=[set[set_effects.Key[20] set_effects.Key[22]]]
set_effects.armed=true
let result=through(set_effects.current)
return if set_effects.current.length=?0 and not set_effects.armed result else 3}'''),
    'generic-nested-return-adjacency': '''pair=():>array<array<int64>>=>[[20 22]]
deep=():>array<array<array<array<int64>>>>=>[[[[20 22]]]]
main=()=>{
let shifted:int64=84 shifted>>=1
if shifted not=? 42 return 1
return pair()[0][0]+deep()[0][0][0][1]}''',
    'generic-nested-return-type-parameter': '''wrap=<T>(value:T):>array<array<T>>=>[[value]]
main=()=>{let narrow:int8=20 let wide:uint64=22
return (wrap(narrow)[0][0] as int64)+(wrap(wide)[0][0] as int64)}''',
    'unpack-dictionary': '''main=()=>{
let [[first x] [second y]]=["a"->20 "b"->22]
return if first=?"a" and second=?"b" x+y else 1}''',
    'unpack-dictionary-entries': '''main=()=>{
let [first _ last]=[100->20 200->99 300->22]
let [key x]=first let [other y]=last
return if key=?100 and other=?300 x+y else 1}''',
    'unpack-dictionary-removed': '''main=()=>{
let values=["a"->20 "gone"->99 "b"->22]
values.remove("gone")
let [[first x] [second y]]=values
values["a"]=0 values.remove("b")
return if first=?"a" and second=?"b" x+y else 1}''',
    'unpack-dictionary-assignment': '''main=()=>{
let x:int64=20 let y:int64=22
let first="a" let second="b"
[[first x] [second y]]=[second->y first->x]
return if first=?"b" and second=?"a" and x=?22 and y=?20 x+y else 1}''',
    'unpack-dictionary-managed': '''main=()=>{
let values=["a"->[20] "b"->[22]]
let [[_ first] [_ second]]=values
let snapshot=first first[0]=99 values["b"][0]=88
return if values["a"][0]=?20 and second[0]=?22 snapshot[0]+second[0] else 1}''',
    'unpack-dictionary-global': '''let calls:int64=0
source=():>dict<uint64 array<int64>>=>{calls+=1 return [uint64.max->[20 22]]}
let [[key [left right]]]=source()
main=()=>{return if calls=?1 and key=?uint64.max left+right else 1}''',
    'unpack-dictionary-nested': '''main=()=>{
let [[[_ [first second]]]]=[["point"->[20 22]]]
return first+second}''',
    'optimizer-nested-exits': '''reachability_probe=(first:bool second:bool):>int64=>{
if first {if second return 20 else return 21} else {return 22}
printl"unreachable tail"
return 99
}
main=()=>{
loop first in [false true] {loop second in [false true] {
let expected=if first (if second 20 else 21) else 22
if reachability_probe(first second) not=? expected return 1
}}
return 42}''',
    'optimizer-nested-exit-rejoin': '''work=(mode:int64):>int64=>{
let result:int64=0
$outer
loop i in [0..4) {
loop j in [0..3) {
if mode =? 0 {if j =? 1 break $outer else continue}
else {if j =? 1 break else result+=1}
result+=100
}
result+=10
}
return result
}
main=()=>{return if work(0)=?0 and work(1)=?444 42 else 1}''',
    'optimizer-nested-exit-managed': '''pick=(mode:int64 values:array<int64>):>array<int64>=>{
let local=values local.push(22)
if mode >? 0 {if mode >? 1 return local else return values}
else {local[0]=99 return local}
panic("unreachable managed tail")
}
main=()=>{let values=[20]
loop i in [0..100) {
if pick(2 values) not=? [20 22] or pick(1 values) not=? [20]
or pick(0 values) not=? [99 22] or values not=? [20] return 1
}
return 42}''',
    'optimizer-jump-table-exits': '''pick=(value:int64):>int64=>{
match value {<0>=>{return 10} <1>=>{return 11} <2>=>{return 12}
<3>=>{return 13} _=>{return 14}}
panic("unreachable match tail")
}
main=()=>{loop i in [-2..6) {
if pick(i) not=? (if i >=? 0 and i <? 4 i+10 else 14) return 1
}
return 42}''',
    'optimizer-constant-selections': '''choose=(flag:bool a:int64 b:int64):>int64=>if flag a else b
offset=(flag:bool x:int64):>int64=>if flag x+1 else x-1
known=(flag:bool x:int64):>int64=>{
if flag return choose(flag x 99)
return choose(flag 99 x)
}
main=()=>{
let calls:int64=0
let next=($capture @calls):>int64=>{calls+=1 return calls}
if choose(true next() next()) not=? 1 or calls not=? 2 return 1
if choose(false next() next()) not=? 4 or calls not=? 4 return 2
let value:int64=20 let saved=choose(true value 99) value=22
if saved+value not=? 42 return 3
if choose(calls >? 2 value value) not=? 22 return 4
if known(true 20)+known(false 22) not=? 42 return 5
return offset(true 20)+offset(false 22)}''',
    'unit-range-guarded-limits': '''bounded_count=(start:int64 stop:int64):>int64=>{
let count:int64=0
loop i in start.. and i <? stop {count+=1 if count >? 10 panic("did not stop")}
return count
}
main=()=>{
let high=int64.max let low=int64.min
let count=bounded_count(high-2 high)+bounded_count(low low+2)+bounded_count(-3 4)
count+=bounded_count(high low)+bounded_count(0 0)
return if count =? 11 42 else 1}''',
    'unit-range-guarded-array': '''bump=(@values:array<int64>):>void=>{
loop i in 0.. and i <? values.length {if i%2 =? 0 continue values[i]+=1}
}
main=()=>{let values=[10 20 11] let snapshot=values bump(@values)
let empty:array<int64>=[] bump(@empty)
return if snapshot =? [10 20 11] and empty.length =? 0 values[0]+values[1]+values[2] else 1}''',
    'unit-range-guarded-changing-stop': '''main=()=>{
let stop:int64=7 let total:int64=0
loop i in 0.. and i <? stop {total+=i if i =? 2 stop=4}
if total not=? 6 return 1
stop=2 total=0
loop i in 0.. and i <? stop {total+=1 if i =? 1 stop=4}
return if total =? 4 42 else 2}''',
    'unit-range-guarded-resize': '''main=()=>{
let values=[0] let count:int64=0
loop i in 0.. and i <? values.length {count+=1 if values.length <? 4 values.push(i)}
if count not=? 4 return 1
values=[0 1 2 3 4 5 6 7] count=0
loop i in 0.. and i <? values.length {count+=1 values.pop()}
return if count =? 4 and values.length =? 4 42 else 2}''',
    'unit-range-guarded-header-effects': '''main=()=>{
let calls:int64=0 let count:int64=0
let limit=($capture @calls):>int64=>{calls+=1 return 3}
loop i in 0.. and i <? limit() {count+=1}
if count not=? 3 or calls not=? 4 return 1
calls=0 count=0
let allowed=($capture @calls):>bool=>{calls+=1 return calls <? 3}
loop i in 0.. and i <? 3 and allowed() {count+=1}
return if count =? 2 and calls =? 3 42 else 2}''',
    'unit-range-guarded-index-write': '''main=()=>{
let count:int64=0
loop i in 0.. and i <? 3 {i=99 count+=1 if count >? 4 panic("index changed control")}
return if count =? 3 42 else 1}''',
    'unit-range-guarded-captured-stop': '''main=()=>{
let stop:int64=4 let count:int64=0
let shrink=($capture @stop)=>{stop=1}
loop i in 0.. and i <? stop {count+=1 shrink()}
return if count =? 1 42 else 1}''',
    'unit-range-guarded-global-alias': '''let shared=[0 1 2]
shrink=():>void=>{shared.pop()}
visit=(@values:array<int64>):>int64=>{
let count:int64=0
loop i in 0.. and i <? values.length {count+=1 shrink()}
return count
}
main=()=>if visit(@shared) =? 2 and shared.length =? 1 42 else 1''',
    'unit-range-guarded-bound-reference': '''visit=(@stop:int64):>int64=>{
let count:int64=0
loop i in 0.. and i <? stop {count+=1 stop=1}
return count
}
main=()=>{let stop:int64=4 return if visit(@stop) =? 1 and stop =? 1 42 else 1}''',
    'unit-range-guarded-else-nested': '''fallback=(stop:int64):>int64=>{
let count:int64=0
loop i in 0.. and i <? stop {count+=1} else {count=42}
return count
}
main=()=>{
let sum:int64=0
loop i in 0.. and i <? 4 {loop j in 0.. and j <? i {sum+=j}}
return if sum =? 4 and fallback(0) =? 42 and fallback(2) =? 2 42 else 1}''',
    'optimizer-parameter-snapshot': '''Box:type=[values:array<array<int64>> label:string]
let shared=Box[[[20] [22]] "old"]
read=(box:Box action:(():>void)):>int64=>{action() return box.values[0][0]+box.values[1][0]}
change=():>void=>{shared.values[0][0]=99 shared.label="new"}
main=()=>{let result=read(shared change)
return if result =? 42 and shared.values[0][0] =? 99 and shared.label =? "new" 42 else 1}''',
    'optimizer-parameter-return': '''Row:type=array<array<string> length=2>
identity=(value:Row):>Row=>value
capture=(value:Row):>(():>Row)=>()=>value
work=():>void=>{let row:Row=[["a"] ["b"]]
let result=identity(row) let get=capture(row)
row[0].push("changed") result[1].push("copy")
if get() not=? [["a"] ["b"]] or result not=? [["a"] ["b" "copy"]] panic("escaped snapshot changed")}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'optimizer-parameter-raw-copy': '''edit=(values:array<int64>):>array<int64>=>{let p=values.data() p[0]=42 return values}
main=()=>{let values=[20 22] values.push(0) let edited=edit(values)
return if values =? [20 22 0] and edited =? [42 22 0] 42 else 1}''',
    'optimizer-interval-guarded-reads': '''inside=(take:bool xs:array<int64>):>bool=>take and xs[0] >=? 0 and xs[0] <=? 42
outside=(skip:bool xs:array<int64>):>bool=>skip or xs[0] <? 0 or xs[0] >? 42
main=()=>{let empty:array<int64>=[]
if inside(false empty) or not outside(true empty) return 1
if not inside(true [42]) or outside(false [42]) return 2
let xs=[20] let calls:int64=0
index=($capture @calls)=>{calls+=1 return 0}
let ok=xs[index()] >=? 0 and xs[index()] <=? 42
if not ok or calls not=? 2 return 3
calls=0
let short=xs[index()] <? 42 or xs[index()] >? 100
return if short and calls =? 1 42 else 4}''',
    'optimizer-interval-effects': '''let calls:int64=0
next=():>int64=>{calls+=1 return calls-1}
probe=(@x:int64):>bool=>x >=? 0 and x <? 4
main=()=>{
let a=next() <? 0 or next() >=? 4
if calls not=? 2 or a return 1
calls=0
let b=next() >=? 0 and next() <? 4
if calls not=? 2 or not b return 2
calls=0
let c=next() <? 1 or next() >=? 4
if calls not=? 1 or not c return 3
let x:int64=2
if not probe(@x) return 4
let narrow:int8=-1
return if narrow <? 0 or narrow >=? 42 42 else 1}''',
    'sort-with-managed': '''Item:type=[score:int64 id:int64 payload:array<int64>]
main=()=>{
let values=[loop i in [0..65) Item[(i*17)%13 i [i]]]
let snapshot=values
let comparisons:int64=0
let descending=true
let less=($capture @comparisons $capture @descending a:Item b:Item):>bool=>{
    comparisons+=1
    return if descending a.score >? b.score else a.score <? b.score
}
loop pass in [0..2) {
    values.sort_with(less)
    loop i in [1..65) {
        let a=values[i-1] let b=values[i]
        if a.score =? b.score and a.id >? b.id return 1
        if descending and a.score <? b.score return 2
        if not descending and a.score >? b.score return 3
    }
    descending=false
}
if comparisons <? 1 return 4
values[0].payload[0]=999
loop i in [0..65) {if snapshot[i].id not=? i or snapshot[i].payload[0] not=? i return 5}
return 42}''',
    'sort-key-stable': '''Item:type=[score:int64 id:int64]
key=(item:Item):>int64=>item.score
main=()=>{
loop size in [0 1 2 15 16 17 31 32 33 129] {
    let items=[loop i in [0..size) Item[(i*17)%13 i]]
    loop descending in [false true] {
        let result=items.sorted_by(key descending)
        if result.length not=? size return 1
        loop i in [1..size) {
            let a=result[i-1] let b=result[i]
            if a.score =? b.score and a.id >? b.id return 2
            if descending and a.score <? b.score return 3
            if not descending and a.score >? b.score return 4
        }
        loop i in [0..size) {if items[i].id not=? i return 5}
    }
}
return 42}''',
    'sort-key-once': '''Item:type=[score:int64 id:int64]
main=()=>{
let calls:array<int64>=[]
let key=($capture @calls item:Item):>int64=>{calls.push(item.id) return item.score}
let items=[loop i in [0..65) Item[65-i i]]
items.sort_by(key)
if calls.length not=? 65 return 1
loop i in [0..65) {
    if calls[i] not=? i or items[i].id not=? 64-i return 2
}
return 42}''',
    'sort-key-managed': '''Item:type=[name:string id:int64 values:array<int64>]
key=(item:Item):>string=>item.name
main=()=>{
let items=[loop i in [0..65) Item[if i%2 =? 0 "beta" else "alpha" i [i]]]
let snapshot=items
items.sort_by(key true)
items[0].values[0]=999
if snapshot[0].values[0] not=? 0 return 1
loop i in [1..33) {if items[i].id not=? i*2 return 2}
loop i in [33..65) {if items[i].id not=? (i-33)*2+1 return 3}
return 42}''',
    'sort-key-float': '''Item:type=[score:float64 id:int64]
main=()=>{let items=[Item[0.0 0] Item[-0.0 1] Item[-2.5 2] Item[1.5 3]]
items.sort_by((item:Item):>float64=>item.score)
return if items[0].id =? 2 and items[1].id =? 0 and items[2].id =? 1 and items[3].id =? 3 42 else 1}''',
    'json-typed-integers': '''Settings:type=[id:uint64 low:int64]
main=()=>{let value=Settings[uint64.max int64.min] let text=to_json(value)
let copy=from_json<Settings>(text)
if copy is? TextError return 1
return if copy.id =? value.id and copy.low =? value.low 42 else 1}''',
    'json-typed-widths': '''Numbers:type=[a:int8 b:int16 c:int32 d:int64 e:uint8 f:uint16 g:uint32 h:uint64]
main=()=>{let value=Numbers[int8.min int16.min int32.min int64.min uint8.max uint16.max uint32.max uint64.max]
let copy=from_json<Numbers>(to_json(value))
if copy is? TextError return 1
return if copy.a =? value.a and copy.b =? value.b and copy.c =? value.c and copy.d =? value.d
and copy.e =? value.e and copy.f =? value.f and copy.g =? value.g and copy.h =? value.h 42 else 1}''',
    'json-typed-floats': '''Numbers:type=[small:float32 tiny:float64 zero:float64]
main=()=>{let value=Numbers[0.1 5e-324 -0.0]
let copy=from_json<Numbers>(to_json(value))
if copy is? TextError return 1
return if copy.small =? value.small and copy.tiny =? value.tiny and 1.0/copy.zero <? 0.0 42 else 1}''',
    'json-typed-nested': '''Item:type=[name:string ids:array<uint64> optional:int64?]
main=()=>{let values=[Item["a\\n🙂" [uint64.max 42] none] Item["b" [] int64.min]]
let copy=from_json<array<Item>>(to_json(values 2))
if copy is? TextError return 1
return if copy.length =? 2 and copy[0].name =? values[0].name and copy[0].ids =? values[0].ids
and copy[0].optional is? none and copy[1].optional =? int64.min 42 else 1}''',
    'json-typed-map': '''main=()=>{let values:dict<string uint64>=["gone"->0 "answer"->uint64.max]
values.remove("gone") values["next"]=42
let copy=from_json<dict<string uint64>>(to_json(values 2))
if copy is? TextError return 1
return if copy.length =? 2 and copy["answer"] =? uint64.max and copy["next"] =? 42 42 else 1}''',
    'json-typed-integer-keys': '''main=()=>{let values:dict<uint64 string>=[uint64.max->"yes"]
let copy=from_json<dict<uint64 string>>(to_json(values))
if copy is? TextError return 1
return if copy[uint64.max] =? "yes" 42 else 1}''',
    'json-typed-empty-record': '''Empty:type=[]
main=()=>{let text=to_json(Empty[])
return if text =? r'{}' 42 else 1}''',
    'json-typed-dynamic-value': '''Holder:type=[value:Json]
main=()=>{let parsed=parse_json(r'{"answer":42}')
if parsed is? JsonError return 1
let text=to_json(Holder[parsed])
return if text =? r'{"value":{"answer":42}}' 42 else 1}''',
    'json-typed-defaults': '''Settings:type=[count:int64=42 label:string="default"]
main=()=>{let loaded=from_json<Settings>(r'{"old":[1,2,3],"label":"kept"}')
if loaded is? TextError return 1
return if loaded.count =? 42 and loaded.label =? "kept" 42 else 1}''',
    'record-spread-basic': '''main=()=>{let base=[left=20 right=1]
let result=[base... right=22]
return if base.right =? 1 result.left+result.right else 1}''',
    'record-spread-only': '''main=()=>{let a=[left=1 right=2] let b=[left=20 right=22]
let merged=[a... b...] let copied=[merged...]
return copied.left+copied.right}''',
    'record-spread-context': '''Pair:type=[left:uint8 right:uint8]
total=(pair:Pair)=>(pair.left as int64)+(pair.right as int64)
main=()=>{let base=Pair[20 1] let typed:Pair=[base... right=22]
return if total([base... right=22]) =? 42 total(typed) else 1}''',
    'record-spread-constructor-argument': '''Pair:type=[left:int64 right:int64]
total=(pair:Pair)=>pair.left+pair.right
main=()=>{let direct=total([Pair[20 22]...])
let anonymous=total([[left=20 right=0]... right=22])
return if direct =? 42 and anonymous =? 42 42 else 1}''',
    'record-spread-overridden-context': '''Answer:type=[value:uint8]
let calls=0
discarded=()=>{calls+=1 return "discarded"}
read=(answer:Answer)=>answer.value as int64
main=()=>{let base=Answer[42] let first:Answer=[value=discarded() base...]
let second=read([value=discarded() base... value=42])
return if calls =? 2 and first.value =? 42 second else 1}''',
    'record-spread-order': '''let trace=0
part=(tag:int64 value:int64)=>{trace=trace*10+tag return [x=value]}
number=(tag:int64 value:int64)=>{trace=trace*10+tag return value}
main=()=>{let result=[x=number(1 0) part(2 1)... x=number(3 2) part(4 42)...]
return if trace =? 1234 result.x else 1}''',
    'record-spread-managed': '''main=()=>{let source=[words=["a"] number=20]
source.words.push("b") let copy=[source... number=22]
copy.words[0]="changed" source.words.push("c")
return if source.words =? ["a" "b" "c"] and copy.words =? ["changed" "b"]
source.number+copy.number else 1}''',
    'record-spread-later-mutation': '''Item:type=[words:array<int64> number:int64]
let source=Item[[20] 1]
change=()=>{source.words[0]=99 return 22}
main=()=>{source.words.push(0) let result=[source... number=change()]
return if result.words =? [20 0] and source.words =? [99 0]
result.words[0]+result.number else 1}''',
    'record-spread-empty': '''Empty:type=[]
main=()=>{let empty=Empty[] let copied=[empty...] let value=[copied... answer=42]
return value.answer}''',
    'record-spread-callback': '''Options:type=[run:((n:int64):>int64) offset:int64]
main=()=>{let base=Options[run=(n:int64)=>n offset=2]
let changed:Options=[base... run=(n)=>n+2]
return changed.run(40)}''',
    'record-spread-generic': '''Box:type=<T>[value:T]
change=<T>(box:Box<T> value:T):>Box<T>=>[box... value=value]
main=()=>{let a=change(Box<int64>[1] 42) let b=change(Box<string>["a"] "b")
return if b.value =? "b" a.value else 1}''',
    'record-spread-overload': '''Small:type=[value:uint8]
Large:type=[value:uint64]
read=(item:Small)=>42
read=(item:Large)=>1
main=()=>{let base=Small[7] return read([base...])}''',
    'generic-value-explicit': '''identity=<T>(x:T):>T=>x
main=()=>{let integer=identity<int64> let text=identity<string>
return if text("yes") =? "yes" integer(42) else 1}''',
    'generic-value-result': '''largest=<T>():>T=>T.max
main=()=>{let limit=largest<uint8> return if limit() =? 255 42 else 1}''',
    'generic-value-callback': '''identity=<T>(x:T):>T=>x
apply=(f:((x:int64):>int64) value:int64)=>f(value)
main=()=>apply(identity<int64> 42)''',
    'generic-value-generic-consumer': '''identity=<T>(x:T):>T=>x
keep=<T>(value:T):>T=>value
main=()=>{let callback=keep(identity<int64>) return callback(42)}''',
    'generic-value-mut': '''replace=<T>(@dest:T value:T):>void=>{dest=value}
main=()=>{let set=replace<int64> let value=0 set(@value 42) return value}''',
    'generic-value-return': '''identity=<T>(x:T):>T=>x
factory=<T>()=>identity<T>
main=()=>{let convert=factory<int64>() return convert(42)}''',
    'generic-value-overload-context': '''choose=<T>(x:T):>T=>x
choose=<T>(x:T y:T):>T=>y
apply=(f:((x:int64):>int64))=>f(42)
main=()=>{let pair:((x:int64 y:int64):>int64)=choose<int64>
return pair(0 apply(choose<int64>))}''',
    'fixed-array-values': '''const WIDTH:int64=2
Pair:type=<T>(array<T length=WIDTH>)
make=(a:int64 b:int64):>Pair<int64>=>[a b]
change=(@value:Pair<int64>):>void=>{value[0]=99}
main=()=>{let before=alloc_count() let pair=make(20 22) let copy=pair
change(@copy)
if pair[0] not=? 20 or copy[0] not=? 99 or pair[end] not=? 22 return 1
let total:int64=0 loop value in pair {total+=value}
return if pair.length =? 2 and alloc_count() =? before total else 2}''',
    'fixed-array-generic-context': '''first=<T>(values:array<T length=2>):>T=>values[0]
main=()=>{let pair:array<uint8 length=2>=[20 22]
return if first(["first" "last"]) =? "first" and pair =? [20 22]
(first(pair) as int64)+(first([22 99])) else 1}''',
    'fixed-array-managed-copies': '''Pair:type=array<array<int64> length=2>
Box:type=[items:Pair]
main=()=>{let pair:Pair=[[20] [22]] let box=Box[pair] let copied=box
copied.items[0].push(99) copied.items[1][0]=0
let dynamic:array<array<int64>>=pair dynamic[0][0]=100
return if pair[0] =? [20] and box.items[1] =? [22]
and copied.items[0] =? [20 99] and copied.items[1] =? [0] 42 else 1}''',
    'fixed-array-loops': '''main=()=>{let pair:array<int64 length=2>=[20 22]
let total:int64=0
loop i in 0.. and value in pair {total+=value+i}
loop value in pair and expected in [20 22] {if value not=? expected return 1}
return total-1}''',
    'fixed-array-dictionary': '''Pair:type=array<int64 length=2>
main=()=>{let values:dict<int64 Pair>=[0->[0 0] 1->[20 22]]
let zero=values.get(0) if zero is? none return 1
let copy=values copy[1][0]=99
if values[1][0] not=? 20 or copy[1][0] not=? 99 return 2
let total:int64=0 loop [key pair] in values {loop value in pair {total+=value}}
return total}''',
    'fixed-array-length-effects': '''Pair:type=array<string length=2>
let calls:int64=0
make=():>Pair=>{calls+=1 return ["first" "last"]}
index=()=>{calls+=10 return 0}
main=()=>{let pairs:array<Pair>=[make()] calls=0
if make().length not=? 2 or calls not=? 1 return 1
if pairs[index()].length not=? 2 or calls not=? 11 return 2
let before=alloc_count()
loop i in [0..20) {if make().len() not=? 2 return 3}
return if alloc_count() =? before and calls =? 31 42 else 4}''',
    'fixed-array-unpack': '''Pair:type=array<int64 length=2>
main=()=>{let pair:Pair=[20 22] let [a b]=pair
[a b]=[b a]
let rows:array<Pair length=2>=[[10 11] [12 9]]
let total:int64=0 loop [left right] in rows {total+=left+right}
let [[x y] [z w]]=rows
return if a =? 22 and b =? 20 and x+y+z+w =? 42 total else 1}''',
    'fixed-array-dynamic-conversion': '''Pair:type=array<array<int64> length=2>
first=<T>(values:array<T length=2>):>T=>values[0]
main=()=>{let source=[[20] [22]] let pair:Pair=source
pair[0].push(99) source[1][0]=0
let back:array<array<int64>>=pair back[0][0]=100
let converted=source as Pair
return if pair[0] =? [20 99] and pair[1] =? [22] and converted[1] =? [0]
and source[0] =? [20] (first(source)[0]+pair[1][0]) else 1}''',
    'fixed-array-dynamic-return': '''Pair:type=array<int64 length=2>
let calls:int64=0
source=()=>{calls+=1 return [20 22]}
make=():>Pair=>source()
main=()=>{let pair=make() let [a b]=pair
return if calls =? 1 a+b else 1}''',
    'fixed-array-slice-update': '''main=()=>{let xs:array<int64 length=6>=[10 20 30 40 50 60] let saved=xs
xs[1..2]=[1 2] xs[..1)=3 xs[4..]=42 xs[3..3)=[]
return if xs =? [3 1 2 40 42 42] and saved =? [10 20 30 40 50 60] 42 else 1}''',
    'fixed-array-selection-update': '''main=()=>{let xs:array<int64 length=6>=[10 20 30 40 50 60]
xs[0,2..]=42 xs[5,3..1]=[1 2 3]
if xs not=? [42 3 42 2 42 1] return 1
let selected=[4 0] xs[selected]=[8 9]
let mask=[false true false true false false] xs[mask]=[20 22]
let r=[5,3..1] xs[r]=7
return if xs =? [9 7 42 7 8 7] 42 else 2}''',
    'fixed-array-update-context': '''main=()=>{let xs:array<uint8 length=4>=[]
xs[..]=12 xs[1..]=[20 21 22] xs[[0 2]]=[3 4] xs[[false true false true]]=5
let rhs:array<uint8 length=2>=[30 40] xs[1..2]=rhs
return if xs =? [3 30 40 5] 42 else 1}''',
    'fixed-array-update-overlap': '''main=()=>{let xs:array<int64 length=4>=[10 20 30 40]
xs[1..3]=xs[..3) if xs not=? [10 10 20 30] return 1
xs[[3 2 1 0]]=xs
return if xs =? [30 20 10 10] 42 else 2}''',
    'fixed-array-update-order': '''let trace:int64=0
start=()=>{trace=trace*10+1 return 0}
stop=()=>{trace=trace*10+2 return 1}
replacement=()=>{trace=trace*10+3 return [20 22]}
main=()=>{let xs:array<int64 length=3>=[] xs[start()..stop()]=replacement()
return if xs =? [20 22 0] and trace =? 123 42 else 1}''',
    'fixed-array-update-parameters': '''Row:type=array<int64 length=2>
change=(xs:Row):>Row=>{xs[..]=0 return xs}
edit=(@xs:Row)=>{xs[..]=42}
main=()=>{let xs:Row=[20 22] let result=change(xs)
if xs not=? [20 22] or result not=? [0 0] return 1
edit(@xs) return if xs =? [42 42] 42 else 2}''',
    'fixed-array-update-places': '''Row:type=array<int64 length=3>
Box:type=[row:Row]
main=()=>{let rows:array<Box>=[Box[[10 20 30]] Box[[40 50 60]]] let saved=rows
let which:int64=0 let calls:int64=0
select=($capture @calls $capture @which)=>{calls+=1 return which}
replace=($capture @which)=>{which=1 return [7 8]}
rows[select()].row[1..end]=replace()
if calls not=? 1 or rows[0].row not=? [10 7 8] or rows[1].row not=? [40 50 60] return 1
let m:dict<string Row>=['a'->[10 20 30]] let old=m
m['a'][0,2..]=[5 6]
return if m['a'] =? [5 20 6] and old['a'] =? [10 20 30]
and saved[0].row =? [10 20 30] 42 else 2}''',
    'fixed-array-update-managed-broadcast': '''main=()=>{let xs:array<array<int64> length=3>=[[1] [2] [3]]
xs[..]=xs[0] xs[1].push(42)
return if xs =? [[1] [1 42] [1]] 42 else 1}''',
    'fixed-array-update-managed': '''Row:type=array<array<string> length=3>
work=():>void=>{let row:Row=[['a'] ['b'] ['c']] let saved=row
row[1..]=[['new'] ['last']] row[0..0]=row[2..2]
row[0].push('!')
if saved not=? [['a'] ['b'] ['c']] or row not=? [['last' '!'] ['new'] ['last']] panic("snapshot changed")
let pool:Pool<Row>=[] let h=pool.add(saved) let old=pool
pool[h][1..]=[['x'] ['y']]
if pool[h] not=? [['a'] ['x'] ['y']] or old[h] not=? saved panic("writeback failed")}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'fixed-array-slices': '''main=()=>{let values:array<int64 length=4>=[10 11 12 9]
let middle=values[1..3) let tail=values[2..] let empty=values[2..2)
if middle not=? [11 12] or tail not=? [12 9] or empty.length not=? 0 return 1
let whole=values[..] whole[0]=99
return if values[0] =? 10 and values[0..1] =? [10 11] and values[1..end] =? [11 12 9] 42 else 2}''',
    'fixed-array-empty-selector': '''main=()=>{let values:array<string length=2>=["a" "b"] let dynamic=[20 22]
let empty=values[[]] let empty_numbers=dynamic[[]]
values[[]]="unused" values[[]]=[] dynamic[[]]=0 dynamic[[]]=[]
return if empty =? [] and empty_numbers =? [] and values =? ["a" "b"] and dynamic =? [20 22] 42 else 1}''',
    'fixed-array-selectors': '''main=()=>{let values=[10 20 30 40]
let indexes:array<int64 length=3>=[3 0 3] let mask:array<bool length=4>=[false true false true]
if values[indexes] not=? [40 10 40] or values[mask] not=? [20 40] return 1
values[indexes]=[1 2 3] values[mask]=42
let inline:array<int64 length=4>=[10 20 30 40]
inline[indexes]=[5 6 7] inline[mask]=[8 9]
return if values =? [2 42 30 42] and inline =? [6 8 30 9] and inline[indexes] =? [9 6 9] 42 else 2}''',
    'fixed-array-selector-snapshots': '''main=()=>{let values:array<int64 length=2>=[1 0]
values[values]=[20 22]
if values not=? [22 20] return 1
let indexes:array<int64 length=2>=[1 0]
replacement=($capture @indexes)=>{indexes[0]=0 return [40 42]}
values[indexes]=replacement()
return if values =? [42 40] and indexes =? [0 0] 42 else 2}''',
    'fixed-array-mask-managed': '''work=():>void=>{let rows:array<array<string> length=3>=[["a"] ["b"] ["c"]]
let mask:array<bool length=3>=[true false true] let saved=rows
let chosen=rows[mask] rows[mask]=[["x"] ["y"]] chosen[0].push("copy")
if rows not=? [["x"] ["b"] ["y"]] or saved not=? [["a"] ["b"] ["c"]] panic("mask snapshot changed")}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'fixed-array-selections': '''main=()=>{let values:array<int64 length=4>=[10 11 12 9]
let backwards=values[end,end-1..0] let odds=values[1,3..]
let picked=values[[3 0 3]] let masked=values[[true false true false]]
let selection=[0,2..3] let selected=values[selection]
return if backwards =? [9 12 11 10] and odds =? [11 9] and picked =? [9 10 9]
and masked =? [10 12] and selected =? [10 12] 42 else 1}''',
    'fixed-array-selection-snapshots': '''Pair:type=array<array<int64> length=2>
let values:Pair=[[20] [22]] let calls:int64=0
indexes=()=>{calls+=1 values[0][0]=99 return [0 1]}
last=()=>{calls+=1 values[1][0]=88 return 1}
main=()=>{let picked=values[indexes()]
if picked not=? [[20] [22]] or values[0][0] not=? 99 return 1
let selected=values[0,1..last()]
return if selected =? [[99] [22]] and values[1][0] =? 88 and calls =? 2 42 else 2}''',
    'fixed-array-slice-snapshots': '''Pair:type=array<array<int64> length=2>
let values:Pair=[[20] [22]] let calls:int64=0
bound=()=>{calls+=1 values[0][0]=99 values[1].push(5) return 2}
main=()=>{let slice=values[0..bound())
slice[0].push(1)
return if calls =? 1 and slice[0] =? [20 1] and slice[1] =? [22]
and values[0] =? [99] and values[1] =? [22 5] 42 else 1}''',
    'fixed-array-slice-loops': '''Pair:type=array<array<int64> length=2>
make=():>Pair=>[[20] [22]]
work=()=>{let total:int64=0 loop value in make()[..] {total+=value[0]}
let values=make() loop i in 0.. and value in values[..] {if value[0] not=? values[i][0] return 1}
loop value in values[..] and expected in [20 22] {if value[0] not=? expected return 2}
return total}
main=()=>{if work() not=? 42 return 1 let before=alloc_count()
loop i in [0..30) {if work() not=? 42 return 2}
return if alloc_count() =? before 42 else 3}''',
    'fixed-array-slice-allocation': '''main=()=>{let values:array<int64 length=4>=[10 11 12 9]
let before=alloc_count() let selected=values[1..3)
return if alloc_count() =? before+1 and selected =? [11 12] 42 else 1}''',
    'fixed-array-spread-context': '''sum=(values:array<uint8 length=2>)=>(values[0] as int64)+(values[1] as int64)
first=<T>(values:array<T length=2>):>T=>values[0]
main=()=>{let pair:array<uint8 length=2>=[20 22]
let values:array<uint8 length=3>=[pair... 99]
let dynamic=[pair...] dynamic[0]=0
let zeros:array<int64 length=2>=[]
return if values[2] =? 99 and pair[0] =? 20 and zeros[0]+zeros[1] =? 0
and first([pair...]) =? 20 sum([[]... 20 22]) else 1}''',
    'fixed-array-cleanup': '''Pair:type=array<array<int64> length=2>
work=()=>{let pair:Pair=[[20] [22]] let copy=pair copy[0].push(1)
let values:array<Pair>=[pair copy] values[0][1][0]=0
return pair[0][0]+pair[1][0]}
main=()=>{if work() not=? 42 return 1 let before=alloc_count()
loop i in [0..30) {if work() not=? 42 return 2}
return if alloc_count() =? before 42 else 3}''',
    'spread-arrays': '''main=()=>{let head=[1 2] let tail=[20 22]
let all=[0 head... 3 tail...]
return if all =? [0 1 2 3 20 22] all[end]+all[end-1] else 1}''',
    'spread-empty-context': '''main=()=>{let empty:array<uint16>=[]
let values:array<uint16>=[empty... []... 42]
let strings:array<string>=[[]... []...]
return if values.length =? 1 and strings.length =? 0 values[0] as int64 else 1}''',
    'spread-call-context': '''total=(xs:array<uint64>)=>xs[0]+xs[1]
main=()=>{let xs:array<uint64>=[20]
return total([xs... 22]) as int64}''',
    'spread-generic': '''append=<T>(xs:array<T> value:T):>array<T>=>[xs... value]
main=()=>{let a=append([20] 22) let b=append(["a"] "b")
return if b =? ["a" "b"] a[0]+a[1] else 1}''',
    'spread-order-snapshot': '''let values=[20 21] let calls=0
source=()=>{calls=calls*10+1 return values}
change=()=>{calls=calls*10+2 values[0]=99 return 22}
main=()=>{values.push(0) let result=[source()... change() values...]
return if calls =? 12 and result =? [20 21 0 22 99 21 0] 42 else 1}''',
    'spread-managed-values': '''Item:type=[words:array<string>]
main=()=>{let xs=[Item[["a"]]] xs.push(Item[["b"]])
let ys=[xs... Item[["c"]]] ys[0].words.push("changed")
xs[1].words[0]="new"
return if xs[0].words =? ["a"] and ys[1].words =? ["b"]
and ys[2].words =? ["c"] 42 else 1}''',
    'spread-grouping': '''main=()=>{let xs=[20 22] let ys=[(xs)...]
let nested=[[xs...] [ys...]]
return nested[0][0]+nested[1][1]}''',
    'end-index-local-offset': '''tail=(xs:array<int64> offset:int64)=>xs[end-offset]
main=()=>{let xs=[1 20 22] let offset=1
let a=tail(xs offset) offset=0
return a+xs[end-offset]}''',
    'end-index-local-slice': '''main=()=>{let xs=[1 2 3 4 5] let offset=2 let step=2
let text="a👩‍🚀é" let one=1
return if xs[end-offset..end] =? [3 4 5]
and xs[end,end-step..0] =? [5 3 1]
and text[end-one..end] =? "👩‍🚀é" 42 else 1}''',
    'end-index-offset-call-mutation': '''let xs=[20 21]
change=()=>{xs[2]=99 return 0}
main=()=>{xs.push(22) let offset=0 let value=xs[end-offset+change()]
return if value =? 22 and xs[2] =? 99 42 else 1}''',
    'end-index-basic': '''main=()=>{let xs=[10 20 22]
return xs[end]+xs[end-1]}''',
    'end-index-once': '''let calls=0
make=()=>{calls+=1 return [20 22]}
main=()=>{let value=make()[end]+make()[end-1]
return if value =? 42 and calls =? 2 42 else 1}''',
    'end-index-nested': '''main=()=>{let xs=[[1 2] [20 22]] let indices=[0 1]
return xs[indices[end]][end]+xs[end][end-1]}''',
    'end-index-slices': '''main=()=>{let xs=[1 2 3 4 5]
return if xs[end-2..end] =? [3 4 5] and xs[..end) =? [1 2 3 4]
and xs[end,end-2..0] =? [5 3 1] and xs[0,2..end] =? [1 3 5] 42 else 1}''',
    'end-index-unicode': '''main=()=>{let text="a👩‍🚀é"
return if text[end] =? "é" and text[end-1..end] =? "👩‍🚀é" 42 else 1}''',
    'end-index-managed-result': '''make=()=>["ab"+"cd" "ef"+"gh"]
main=()=>{let text=make()[end] let tail=make()[end-1..end]
return if text =? "efgh" and tail =? ["abcd" "efgh"] 42 else 1}''',
    'end-index-empty-slices': '''main=()=>{let xs:array<int64>=[] let text=""
return if xs[..end].length =? 0 and text[..end] =? "" 42 else 1}''',
    'end-index-read-mutation': '''let xs=[20 21]
change=()=>{xs[2]=99 return 0}
main=()=>{xs.push(22) let value=xs[end+change()]
return if value =? 22 and xs[2] =? 99 42 else 1}''',
    'end-index-length-mutation': '''Series:type=[values:array<int64>]
let source=Series[[20 22]]
len=(s:Series)=>{source.values[1]=99 return s.values.length}
__index__=(s:Series i:int64)=>s.values[i]
main=()=>{source.values.push(0) let value=source[end-1]
return if value =? 22 and source.values[1] =? 99 42 else 1}''',
    'end-index-update': '''main=()=>{let xs=[1 20] xs.push(21) let saved=xs
xs[end]+=1 xs[end-1]=20
return if xs[end]+xs[end-1] =? 42 and saved =? [1 20 21] 42 else 1}''',
    'end-index-update-nested': '''let calls=0
index=()=>{calls+=1 return 0}
main=()=>{let xs=[[1 20 21]] xs.push([0]) let saved=xs
xs[index()][end]+=1
return if calls =? 1 and xs[0][end] =? 22 and saved[0][end] =? 21 42 else 1}''',
    'end-index-update-slice': '''main=()=>{let xs=[1 2 3 4 5]
xs[end-2..end]=[20 21 22] xs[0,2..end]=7
return if xs =? [7 2 7 21 7] 42 else 1}''',
    'end-index-update-order': '''let xs=[10 20 21]
rhs=()=>{xs.push(999) return 1}
main=()=>{xs[end]+=rhs()
return if xs =? [10 20 22 999] 42 else 1}''',
    'end-index-sequence': '''Series:type=[values:array<int64>]
len=(s:Series)=>s.values.length
__index__=(s:Series i:int64)=>s.values[i]
__setindex__=(@s:Series i:int64 value:int64)=>{s.values[i]=value}
main=()=>{let s=Series[[20 21]] s[end]+=1 return s[end]+s[end-1]}''',
    'end-index-length-once': '''Series:type=[values:array<int64>]
let lengths=0 let sources=0
len=(s:Series)=>{lengths+=1 return s.values.length}
__index__=(s:Series i:int64)=>s.values[i]
make=()=>{sources+=1 return Series[[20 22]]}
main=()=>{let value=make()[end+end-1]
return if value =? 22 and sources =? 1 and lengths =? 1 42 else 1}''',
    'end-index-custom-parent': '''Outer:type=[values:array<array<int64>>]
let gets=0 let sets=0 let indices=0
index=()=>{indices+=1 return 0}
__index__=(s:Outer i:int64)=>{gets+=1 return s.values[i]}
__setindex__=(@s:Outer i:int64 value:array<int64>)=>{sets+=1 s.values[i]=value}
main=()=>{let s=Outer[[[20 21]]] s[index()][end]+=1
return if gets =? 1 and sets =? 1 and indices =? 1 and s.values[0] =? [20 22] 42 else 1}''',
    'end-index-global-name': '''let end=20
main=()=>{let xs=[20 22] return end+xs[end]}''',
    'end-index-double-update': '''main=()=>{let xs=[[1] [20 21]]
xs[end][end]+=1 return xs[end][0]+xs[end][end]}''',
    'end-index-parameter-copy': '''change=(xs:array<int64>)=>{xs[end]=0 return xs}
main=()=>{let xs=[20 22] xs.push(42) let changed=change(xs)
return if changed =? [20 22 0] and xs =? [20 22 42] 42 else 1}''',
    'compound-resize-storage': '''let xs=[10 20 21] let i=2
rhs=()=>{xs.push(999) i=0 return 1}
main=()=>{xs[i]+=rhs()
return if xs =? [10 20 22 999] 42 else 1}''',
    'compound-resize-record-storage': '''Item:type=[value:int64]
let xs=[Item[21]]
rhs=()=>{xs.push(Item[999]) return 1}
main=()=>{xs[0].value+=rhs()
return if xs[0].value =? 22 and xs[1].value =? 999 42 else 1}''',
    'numeric-names': '''main=()=>{let x=42
return if int8(x) =? 42 and int16(x) =? 42 and int32(x) =? 42 and int64(x) =? 42
and uint8(x) =? 42 and uint16(x) =? 42 and uint32(x) =? 42 and uint64(x) =? 42
and float32(x) =? 42.0 and float64(x) =? 42.0 and string(x) =? "42" 42 else 1}''',
    'numeric-bounds': '''main=()=>{
if int8.min not=? -128 or int8.max not=? 127 return 1
if int16.min not=? -32768 or int16.max not=? 32767 return 2
if int32.min not=? -2147483648 or int32.max not=? 2147483647 return 3
if int64.min not=? -9223372036854775808 or int64.max not=? 9223372036854775807 return 4
if uint8.min not=? 0 or uint8.max not=? 255 return 5
if uint16.min not=? 0 or uint16.max not=? 65535 return 6
if uint32.min not=? 0 or uint32.max not=? 4294967295 return 7
if uint64.min not=? 0 or uint64.max not=? 18446744073709551615 return 8
return 42}''',
    'numeric-bounds-generic': '''upper=<T>():>T=>T.max
lower=<T>():>T=>T.min
Byte:type=uint8
main=()=>{let a:Byte=upper<Byte>() let b:int16=lower<int16>()
return if a =? 255 and b =? -32768 and upper<uint64>() =? 18446744073709551615 42 else 1}''',
    'numeric-bounds-alias': '''Byte:type=uint8
Word:type=uint64
Number:type=<T>(T)
const TOP=Word.max
main=()=>{let a:Byte=Byte.max let b:int16=Number<int16>.min
return if a =? 255 and b =? -32768 and TOP =? 18446744073709551615 42 else 1}''',
    'generic-type-value-alias': '''Record:type=[value:int64]
Alias:type=Record
Identity:type=<T>(T)
main=()=>Alias[20].value+Identity<Record>[22].value''',
    'numeric-bounds-constant': '''const BYTE_TOP=uint8.max
const WORD_TOP=uint64.max
width=((x:uint8)=>8)&((x:uint64)=>64)&((x:int64)=>0)
default_byte=(x:uint8=BYTE_TOP)=>x
main=()=>{let x=BYTE_TOP let y=WORD_TOP
return if width(x) =? 8 and width(y) =? 64 and default_byte() =? 255 42 else 1}''',
    'numeric-names-shadow': '''main=()=>{let uint8=(x:int64)=>x+2
let int64=[min=20 max=22]
return if uint8(40) =? int64.min+int64.max 42 else 1}''',
    'sequence-unpack': '''Series:type=[values:array<array<int64>>]
len=(s:Series)=>s.values.length
__index__=(s:Series index:int64)=>s.values[index]
main=()=>{let total=0 loop [a b] in Series[[[10 11] [9 12]]] total+=a+b return total}''',
    'sequence-closures': '''Series:type=[first:int64 count:int64]
len=(s:Series)=>s.count
__index__=(s:Series index:int64)=>s.first+index
main=()=>{let callbacks=[loop x in Series[13 3] ()=>x]
return if callbacks[0]() =? 13 and callbacks[1]() =? 14 and callbacks[2]() =? 15 42 else 1}''',
    'sequence-basic': '''Series:type=[first:int64 count:int64]
len=(s:Series)=>s.count
__index__=(s:Series index:int64)=>s.first+index
main=()=>{let total=0 loop x in Series[13 3] total+=x return total}''',
    'sequence-once': '''Series:type=[first:int64 count:int64]
let made:int64=0 let lengths:int64=0 let reads:int64=0
make=()=>{made+=1 return Series[13 3]}
len=(s:Series)=>{lengths+=1 return s.count}
__index__=(s:Series index:int64)=>{reads+=1 return s.first+index}
main=()=>{let total=0 loop x in make() total+=x
return if total =? 42 and made =? 1 and lengths =? 1 and reads =? 3 42 else 1}''',
    'sequence-snapshot': '''Series:type=[values:array<int64>]
len=(s:Series)=>s.values.length
__index__=(s:Series index:int64)=>s.values[index]
let source=Series[[20 22]]
main=()=>{source.values.push(0) let total=0
loop x in source {total+=x source.values[0]=999 source.values.push(1)}
return if total =? 42 and source.values.length =? 6 42 else 1}''',
    'sequence-comprehension': '''Series:type=<T>[values:array<T>]
len=<T>(s:Series<T>)=>s.values.length
__index__=<T>(s:Series<T> index:int64):>T=>s.values[index]
main=()=>{let source=Series<string>[["a" "bb" "ccc"]]
let lengths=[loop text in source text.length]
return if lengths =? [1 2 3] 42 else 1}''',
    'sequence-counted': '''Series:type=[first:int64 count:int64]
len=(s:Series)=>s.count
__index__=(s:Series index:int64)=>s.first+index
main=()=>{let total=0 loop i in 0.. and x in Series[12 3] total+=i+x return total}''',
    'sequence-combined': '''Series:type=[first:int64 count:int64]
len=(s:Series)=>s.count
__index__=(s:Series index:int64)=>s.first+index
main=()=>{let both=0 let either=0
loop x in Series[13 3] and y in Series[1 2] both+=x+y
loop x in Series[13 3] or y in Series[1 2] either+=(x??0)+(y??0)
return if both =? 30 and either =? 45 42 else 1}''',
    'sequence-flow': '''Series:type=[first:int64 count:int64]
len=(s:Series)=>s.count
__index__=(s:Series index:int64)=>s.first+index
main=()=>{let total=0
loop x in Series[0 0] {total=999} else {total+=40}
$outer loop x in Series[0 3] {
    loop y in Series[0 3] {
        total+=1
        if x =? 0 continue $outer
        break $outer
    }
}
return total}''',
    'sequence-cleanup': '''Series:type=<T>[values:array<T>]
len=<T>(s:Series<T>)=>s.values.length
__index__=<T>(s:Series<T> index:int64):>T=>s.values[index]
work=():>string=>{let source=Series<string>[["a" "b"]] source.values.push("c")
loop text in source {if text =? "a" continue return text} else {return "empty"}
return "end"}
main=()=>{work() let before=alloc_count()
loop i in [0..20) {if work() not=? "b" return 1}
return if alloc_count() =? before 42 else 2}''',
    'slice-update-bounds': '''main=()=>{
let xs=[10 20 30 40 50] xs.push(60) let saved=xs
xs[1..2]=[1 2] xs[..1)=3 xs[4..]=42 xs[3..3)=[]
return if xs =? [3 1 2 40 42 42] and saved =? [10 20 30 40 50 60] 42 else 1
}''',
    'slice-update-whole': '''main=()=>{
let xs=[1 2 3] xs[..]=[10 20 30] xs[..]=42
let empty:array<int64>=[] empty[..]=42 empty[..]=[]
return if xs =? [42 42 42] and empty =? [] 42 else 1
}''',
    'slice-update-overlap': '''main=()=>{
let xs=[10 20 30 40] xs.push(50) let saved=xs
xs[1..3]=xs[..3)
return if xs =? [10 10 20 30 50] and saved =? [10 20 30 40 50] 42 else 1
}''',
    'slice-update-order': '''let trace:int64=0
start=()=>{trace=trace*10+1 return 0}
stop=()=>{trace=trace*10+2 return 1}
replacement=()=>{trace=trace*10+3 return [20 22]}
main=()=>{let xs=[0 0 0] xs[start()..stop()]=replacement()
return if xs =? [20 22 0] and trace =? 123 42 else 1
}''',
    'slice-update-managed': '''work=():>void=>{
let pool:Pool<array<string>>=[] let h=pool.add(["a" "b" "c"])
let saved=pool pool[h][1..]=["new" "last"]
if pool[h] not=? ["a" "new" "last"] or saved[h] not=? ["a" "b" "c"] panic("snapshot changed")
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'range-index-stepped-slices': '''main=()=>{
let xs=[10 20 30 40 50 60] let empty:array<int64>=[]
return if xs[0,2..] =? [10 30 50] and xs[5,3..] =? [60 40 20]
and xs[0,2..4) =? [10 30] and xs[0,2..4] =? [10 30 50]
and xs[5,3..1] =? [60 40 20] and xs[5,3..1) =? [60 40]
and empty[0,2..] =? [] 42 else 1
}''',
    'range-index-stepped-update': '''main=()=>{
let xs=[10 20 30 40 50] xs.push(60) let saved=xs
xs[0,2..]=42 xs[5,3..1]=[1 2 3]
return if xs =? [42 3 42 2 42 1] and saved =? [10 20 30 40 50 60] 42 else 1
}''',
    'range-index-stepped-overlap': '''main=()=>{
let xs=[10 20 30 40] xs.push(50) xs[4,3..]=xs
return if xs =? [50 40 30 20 10] 42 else 1
}''',
    'range-index-stepped-snapshot': '''let xs:array<int64>=[10 20 30] let trace:int64=0
first=()=>{trace=trace*10+1 xs[0]=999 return 0}
second=()=>{trace=trace*10+2 return 2}
last=()=>{trace=trace*10+3 return 2}
main=()=>{xs.push(40) let result=xs[first(),second()..last()]
return if result =? [10 30] and xs[0] =? 999 and trace =? 123 42 else 1}''',
    'range-index-stepped-pool': '''main=()=>{
let pool:Pool<array<int64>>=[] let h=pool.add([10 20 30 40]) let saved=pool
pool[h][0,2..]=42
return if pool[h] =? [42 20 42 40] and saved[h] =? [10 20 30 40] 42 else 1
}''',
    'range-index-values': '''main=()=>{
let xs=[10 20 30 40 50] let forward=[0,2..4] let reverse=[4,2..0] let empty=[2..2)
return if xs[forward] =? [10 30 50] and xs[reverse] =? [50 30 10] and xs[empty] =? [] 42 else 1
}''',
    'range-index-boundaries': '''main=()=>{
let xs=[10 20 30 40 50]
return if xs[(0,2..4]] =? [30 50] and xs[[4,2..0)] =? [50 30]
and xs[(4,2..0)] =? [30] and xs[[0..5)] =? xs 42 else 1
}''',
    'range-index-update': '''main=()=>{
let xs=[10 20 30 40 50] xs.push(60) let saved=xs let selected=[0,2..4]
xs[selected]=42
xs[[5,3..1]]=[1 2 3]
return if xs =? [42 3 42 2 42 1] and saved =? [10 20 30 40 50 60] 42 else 1
}''',
    'range-index-overlap': '''main=()=>{
let xs=[10 20 30 40] xs.push(50) let reverse=[4,3..0]
xs[reverse]=xs
return if xs =? [50 40 30 20 10] 42 else 1
}''',
    'range-index-generic': '''select=<T>(xs:array<T> indices:IntRange):>array<T>=>xs[indices]
main=()=>{let xs=["a" "b" "c"] let picked=select(xs [0,2..2]) picked[0]="new"
return if picked =? ["new" "c"] and xs =? ["a" "b" "c"] 42 else 1}''',
    'range-index-snapshot-order': '''let xs:array<int64>=[10 20 30] let calls:int64=0
indices=():>IntRange=>{calls+=1 xs[0]=999 return [0,2..2]}
main=()=>{xs.push(40) let result=xs[indices()]
return if result =? [10 30] and xs[0] =? 999 and calls =? 1 42 else 1}''',
    'range-index-cleanup': '''work=():>void=>{
let xs=["a" "b" "c"] xs.push("d") let saved=xs let picked=xs[[3,1..0]]
xs[[0,2..2]]=picked
if xs not=? ["d" "b" "b" "d"] or saved not=? ["a" "b" "c" "d"] panic("snapshot changed")
}
main=()=>{work() let before=alloc_count() loop i in [0..20) work()
return if alloc_count() =? before 42 else 1}''',
    'coalesce-inferred-none': 'main=()=>none??42',
    'coalesce-basic': '''read=(present:bool):>int64?=>if present 42 else none
main=()=>if (read(true)??0) =? 42 and (read(false)??42) =? 42 42 else 1''',
    'coalesce-lazy-order': '''let trace:int64=0
read=(present:bool):>int64?=>{trace=trace*10+1 if present 42 else none}
fallback=()=>{trace=trace*10+2 42}
main=()=>{let a=read(true)??fallback() let b=read(false)??fallback()
return if a =? 42 and b =? 42 and trace =? 112 42 else 1}''',
    'coalesce-chain': '''read=(value:int64):>int64?=>if value >? 0 value else none
main=()=>{let a=read(0)??read(0)??42 let b:int64?=read(0)??read(42)
let c:int64?=read(0)??read(0)
return if a =? 42 and b =? 42 and c is? none 42 else 1}''',
    'coalesce-precedence': '''read=():>int64?=>none
main=()=>if read()??20+22 =? 42 and read()??2^3 =? 8 42 else 1''',
    'coalesce-false': '''let called:bool=false
read=():>bool?=>false
fallback=()=>{called=true true}
main=()=>if not (read()??fallback()) and not called 42 else 1''',
    'coalesce-context': '''choose=(value:int64?):>int64=>value??42
main=()=>{let bytes:array<uint8>=none??[20 22]
return if choose(none) =? 42 and bytes[0]+bytes[1] =? 42 42 else 1}''',
    'coalesce-generic': '''or_else=<T>(value:T? fallback:(():>T)):>T=>value??fallback()
main=()=>if or_else(none ()=>42) =? 42 and or_else("yes" ()=>"no") =? "yes" 42 else 1''',
    'coalesce-managed': '''make=(present:bool):>array<string>?=>{
let values=["a"] values.push("b") return if present values else none
}
work=(present:bool):>void=>{
let source=make(present) let values=source??["fallback"] let saved=values
values.push("new")
if present {if saved not=? ["a" "b"] panic("snapshot changed")}
else {if saved not=? ["fallback"] panic("fallback changed")}
}
main=()=>{work(true) work(false) let before=alloc_count()
loop i in [0..20) {work(true) work(false)}
return if alloc_count() =? before 42 else 1}''',
    'compound-value-parameter': 'halve=(x:int64)=>{x//=2 x}\nmain=()=>{let x=84 return if halve(x) =? 42 and x =? 84 42 else 1}',
    'compound-custom-width': '''Box:type=[value:int8]
__index__=(box:Box i:int64):>int8=>box.value
__setindex__=(@box:Box i:int64 value:int8):>void=>{box.value=value}
main=()=>{let box=Box[-128] box[0]//=-1 box[0]%=3
return if box.value =? 1 42 else 1}''',
    'compound-protocols': '''Box:type=[value:int64]
__floordiv__=(a:Box b:int64)=>Box[a.value+b]
__mod__=(a:Box b:int64)=>Box[a.value+b]
__truediv__=(a:Box b:int64)=>Box[a.value+b]
__pow__=(a:Box b:int64)=>Box[a.value+b]
main=()=>{let value=Box[10] value//=2 value%=8 value/=2 value^=20 return value.value}''',
    'compound-managed-lifetime': '''work=():>void=>{
let values=[3/2] values.push(5/2) let saved=values
loop i in [0..20) {values[0]/=3 values[0]^=(-1)}
if saved not=? [3/2 5/2] panic("snapshot changed")
}
main=()=>{work() let before=alloc_count() loop i in [0..10) work()
return if alloc_count() =? before 42 else 1}''',
    'compound-floor-signs': '''main=()=>{
let a=-7 let b=7 let c=-7 let d=7
let e=-7 let f=7 let g=-7 let h=7
a//=3 b//=-3 c//=-3 d//=3
e%=3 f%=-3 g%=-3 h%=3
return if [a b c d e f g h] =? [-3 -3 2 2 2 -2 -1 1] 42 else 1
}''',
    'compound-widths': '''main=()=>{
let a:int8=-128 let b:uint64=18446744073709551615 let c:int64=-9223372036854775808
let d:int16=-17 let e:uint8=3
a//=-1 b//=2 c//=-1 d%=8 e^=3
return if a =? -128 and b =? 9223372036854775807 and c =? -9223372036854775808
and d =? 7 and e =? 27 42 else 1
}''',
    'compound-exact': '''main=()=>{
let fraction=3/2 fraction/=3 fraction^=(-2)
let big=123456789012345678901234567890 big//=10 big%=100 big^=2
let float:float32=9.0 float/=2 float^=2
return if fraction =? 4 and big =? 7921 and float =? 20.25 42 else 1
}''',
    'compound-order': '''let value:int64=84 let calls:int64=0
change=()=>{calls+=1 value=999 return 2}
main=()=>{value//=change() return if value =? 42 and calls =? 1 42 else 1}''',
    'compound-array-place': '''let values:array<int64>=[84 100] let index:int64=0 let calls:int64=0
pick=()=>{calls+=1 return index}
change=()=>{index=1 values[0]=999 return 2}
main=()=>{values.push(200) let saved=values
values[pick()]//=change()
return if values =? [42 100 200] and saved =? [84 100 200] and calls =? 1 42 else 1}''',
    'compound-index-variable': '''let values:array<int64>=[84 100] let index:int64=0
change=()=>{index=1 return 2}
main=()=>{values.push(200) values[index]//=change()
return if values =? [42 100 200] 42 else 1}''',
    'compound-nested-place': '''Item:type=[values:array<int64>]
let order:int64=0
outer=()=>{order=order*10+1 return 0}
inner=()=>{order=order*10+2 return 0}
right=()=>{order=order*10+3 return 2}
main=()=>{let values=[Item[[84]] Item[[10]]] values.push(Item[[20]])
values[outer()].values[inner()]//=right()
return if order =? 123 and values[0].values[0] =? 42 42 else 1}''',
    'compound-custom-index': '''Box:type=[values:array<int64>]
let reads:int64=0 let writes:int64=0 let index:int64=0
__index__=(box:Box i:int64):>int64=>{reads+=1 return box.values[i]}
__setindex__=(@box:Box i:int64 value:int64):>void=>{writes+=1 box.values[i]=value}
change=()=>{index=1 return 2}
main=()=>{let box=Box[[84 100]] box[index]//=change()
return if box.values =? [42 100] and reads =? 1 and writes =? 1 42 else 1}''',
    'compound-map': '''let key:string="first"
change=()=>{key="second" return 2}
main=()=>{let values=["first"->84 "second"->100] let saved=values
values[key]//=change() values["missing"]%=3
return if values["first"] =? 42 and values["second"] =? 100 and values["missing"] =? 0
and saved["first"] =? 84 and saved.length =? 2 42 else 1}''',
    'compound-pool': '''main=()=>{
let pool:Pool<array<int64>>=[] let h=pool.add([84]) let saved=pool
pool[h][0]//=2
return if pool[h][0] =? 42 and saved[h][0] =? 84 42 else 1}''',
    'compound-generic': '''update=<T>(@value:T divisor:T):>void=>{value//=divisor value%=divisor value^=3}
main=()=>{let a=-17 update(@a 3) let b=123456789012345678901234567890 let expected=(b//3%3)^3 update(@b 3)
return if a =? 0 and b =? expected 42 else 1}''',
    'loop-else-conditions': '''main=()=>{
let total=0 let calls=0
loop {calls+=1; false} {total=999} else {total+=10}
loop {calls+=1; calls <? 4} {total+=1 continue} else {total=999}
loop true {total+=30 break} else {total=999}
return if calls =? 4 total else 1
}''',
    'loop-else-chains': '''main=()=>{
let total=0 let empty:array<int64>=[]
if false {total=999}
else loop value in empty {total=999}
else if false {total=999}
else loop value in [20 22] {total+=value}
else {total=999}
return total
}''',
    'loop-else-iterators': '''main=()=>{
let total=0 let empty=[3..3) let full=(0,2..4] let missing:array<int64>=[]
loop value in empty {total=999} else {total+=10}
loop value in full and value <? 2 {total=999} else {total+=10}
loop c in "" {total=999} else {total+=10}
loop c in "é🙂" {total+=1} else {total=999}
loop x in [1] and y in missing {total=999} else {total+=10}
return total
}''',
    'loop-else-labels': '''main=()=>{
let total=0
$outer
loop i in [0..3) {
    $inner
    loop j in [0..2) {
        total+=1
        if i =? 0 {continue $outer}
        if i =? 1 {break $inner}
        break $outer
    } else {total=999}
    total+=10
} else {total=999}
return if total =? 13 42 else 1
}''',
    'loop-else-comprehensions': '''main=()=>{
let a=[loop x in [0..0) x else 42]
let b=[loop x in [1..3] x else 999]
let c=[loop x in [0..0) x else loop y in [0..0) y else 42]
return if a =? [42] and b =? [1 2 3] and c =? [42] 42 else 1
}''',
    'loop-else-generic': '''head_or=<T>(values:array<T> fallback:T):>T=>{
loop value in values {return value} else {return fallback}
}
main=()=>if head_or([42] 0) =? 42 and head_or([] "empty") =? "empty" 42 else 1''',
    'loop-else-or': '''main=()=>{
let empty:array<int64>=[] let total=0
loop x in empty or y in empty {total=999} else {total+=40}
loop x in empty or y in [10 20] {total+=1} else {total=999}
return total
}''',
    'loop-else-return-chains': '''choose=(take:bool):>int64=>{
if take {return 42}
else loop x in [0..0) {return x}
else loop c in "a" {if c =? "a" {return 42} else {return 1}}
else {return 2}
}
main=()=>if choose(true) =? 42 and choose(false) =? 42 42 else 1''',
    'loop-else-cleanup': '''work=(empty:bool):>int64=>{
let source:array<string>=if empty [] else ["x"]
loop text in source {
    let values=["body {text}"] values.push(text)
    return values.length
} else {
    let values=["fallback {empty}"] values.push("y")
    return values.length
}
}
main=()=>{
work(true) work(false) let before=alloc_count()
loop i in [0..20) {if work(i%2 =? 0) not=? 2 return 1}
return if alloc_count() =? before 42 else 2
}''',
    'optimizer-record-wide-integers': '''Pair:type=[x:int64 y:int64]
advance=(p:Pair):>Pair=>Pair(x=p.x+1 y=p.y-2)
main=()=>{
let p=Pair(x=4294967296 y=-4294967296) let saved=p
loop i in [0..20) {p=advance(p)}
let values=[saved p] values.push(p)
p.x=99
return if saved.x =? 4294967296 and saved.y =? (-4294967296)
and values[1].x =? 4294967316 and values[2].y =? (-4294967336) 42 else 1
}''',
    'optimizer-record-wide-floats': '''Pair:type=[x:float64 y:float64]
advance=(p:Pair):>Pair=>Pair(x=p.x+0.5 y=p.y+p.x)
main=()=>{
let p=Pair(x=2.5 y=1.25) let saved=p
loop i in [0..20) {p=advance(p)}
let values=[saved p] values.push(p)
p.y=0.0
let precise=advance(Pair(x=1.0000000000000002 y=0.0))
return if saved.x =? 2.5 and saved.y =? 1.25 and precise.y >? 1.0
and values[1].x =? 12.5 and values[2].y =? 146.25 42 else 1
}''',
    'optimizer-record-wide-mixed': '''Pair:type=[x:int64 y:float64]
advance=(p:Pair):>Pair=>Pair(x=p.x+1 y=p.y+0.25)
choose=(take:bool):>Pair=>{let p:Pair=[] if take {p=Pair(x=4294967296 y=2.5)} return p}
main=()=>{
let zero=choose(false) let p=choose(true)
loop i in [0..20) {p=advance(p)}
return if zero.x =? 0 and zero.y =? 0.0 and p.x =? 4294967316 and p.y =? 7.5 42 else 1
}''',
    'optimizer-record-mixed-widths': '''Pair:type=[x:int32 y:int64]
Outer:type=[left:Pair right:Pair]
advance=(p:Pair):>Pair=>Pair(x=p.x+1 y=p.y-2)
main=()=>{
let p=Pair(x=-2147483648 y=4294967296)
let outer=Outer(left=p right=p)
loop i in [0..20) {p=advance(p)}
outer.right=p
return if outer.left.x =? (-2147483648) and outer.left.y =? 4294967296
and outer.right.x =? (-2147483628) and outer.right.y =? 4294967256 42 else 1
}''',
    **{f'loop-label-original-{name}': (Path(__file__).resolve().parents[2] / 'dewy/tests' / f'{name}.dewy').read_text()
       for name in ['iterator_labeled_exits', 'range_stepped_labeled_exits']},
    'loop-label-while': '''main=()=>{
let count:int64=0 let result:int64=0
$outer
loop true {
    count+=1
    loop true {
        if count <? 3 {continue $outer}
        result=42
        break $outer
    }
}
return result
}''',
    'loop-label-cursors': '''main=()=>{
let r=(0,2..8] let total:int64=0
$outer
loop x in r {
    loop c in "a🙂" {
        if x =? 2 {total+=2 continue $outer}
        if x =? 4 {total+=10 break}
        total+=30 break $outer
    }
}
return total
}''',
    'loop-label-string-outer': '''main=()=>{
let total:int64=0
$letters
loop c in "ab🙂" {
    loop i in [0..2] {
        if c =? "a" {total+=2 continue $letters}
        if c =? "b" {total+=10 break}
        total+=30 break $letters
    }
}
return total
}''',
    'loop-label-reuse': '''run=<T>(value:T):>int64=>{
$again
loop x in [1] {loop y in [1] {break $again}}
$again
loop true {break $again}
return 21
}
main=()=>run(1)+run("hello")''',
    'loop-label-combined': '''main=()=>{
let total=0
$range
loop x in [0..4) and x <? 3 {
    loop y in [0..2) {total+=1 continue $range}
}
$array
loop x in [1 2 3] and x <? 3 {
    loop y in [0..2) {total+=2 continue $array}
}
$zip
loop x in [1 2 3] and y in [4 5 6] {
    loop z in [0..2) {total+=3 continue $zip}
}
$longest
loop x in [1] or y in [2 3 4] {
    loop z in [0..2) {total+=4 continue $longest}
}
return if total =? 28 42 else 1
}''',
    'loop-label-cleanup': '''work=()=>{
let result:int64=0
$outer
loop i in [0..3) {
    let text="iteration {i}" let values=[text] values.push(text)
    loop j in [0..3) {
        let more=[values] more.push(values)
        result+=values.length+more.length
        if i =? 0 {continue $outer}
        break $outer
    }
}
return result
}
main=()=>{
work() let before=alloc_count()
loop i in [0..20) {if work() not=? 8 return 1}
return if alloc_count() =? before 42 else 2
}''',
    **{f'stored-range-original-{name}': (Path(__file__).resolve().parents[2] / 'dewy/tests' / f'{name}.dewy').read_text()
       for name in ['range_values', 'range_bound_forms', 'range_stepped']},
    'stored-range-exclusive-first': '''main=()=>{
let up=(0,3..10] let down=(10,7..0) let singleton=(5..5] let adjacent=(5..6)
let a=[loop x in up x] let b=[loop x in down x]
let c=[loop x in singleton x] let d=[loop x in adjacent x]
let combined:int64=0 loop x in (0..3] and y in (10,8..4] {combined+=x+y}
return if a =? [3 6 9] and b =? [7 4 1] and c.length =? 0 and d.length =? 0
and 0 notin? up and 3 in? up and 10 notin? down and 7 in? down and combined =? 24 42 else 1
}''',
    'stored-range-exclusive-limits': '''main=()=>{
let low:int64=-9223372036854775808 let high:int64=9223372036854775807
let all=(low..high] let empty=(high..high] let reverse=(high,low..low]
let a=[loop x in empty x] let b=[loop x in reverse x]
let first:int64=0 loop x in all {first=x break}
return if low notin? all and high in? all and first =? low+1 and a.length =? 0
and b =? [low] and low in? reverse and high notin? reverse 42 else 1
}''',
    'overload-group-empty-receiver': '''Value:type=[answer:int64=1]
consume=(values:array<int64>)=>42
consume=(value:Value)=>value.answer
main=()=>[].consume()''',
    'stored-range-reuse': '''window=[0..10)
evens=0,2..100
sum=(r:IntRange):>int64=>{let total:int64=0 loop x in r {total+=x} return total}
main=()=>{
let local=[3..6]
let count:int64=0 loop x in evens {count+=1}
return if sum(window) =? 45 and sum(local) =? 18 and sum(local) =? 18
and count =? 51 and 16 in? evens and 15 notin? evens 42 else 1
}''',
    'stored-range-direction': '''main=()=>{
let up=[1,4..11] let down=[8,5..0) let empty=[4..2] let wrong=[1,-1..8]
let a=[loop x in up x] let b=[loop x in down x]
let c=[loop x in empty x] let d=[loop x in wrong x]
return if a =? [1 4 7 10] and b =? [8 5 2] and c.length =? 0 and d.length =? 0
and 10 in? up and 11 notin? up and 5 in? down and 0 notin? down and 4 notin? empty
and 7 in? [1,4..11] and 8 notin? [1,4..11] 42 else 1
}''',
    'stored-range-boundaries': '''main=()=>{
let low:int64=-9223372036854775808 let high:int64=9223372036854775807
let all=[low..high] let wide=[low,high..high] let reverse=[high,low..low]
let a=[loop x in wide x] let b=[loop x in reverse x]
let count:int64=0 loop x in all {count+=1 if count =? 3 break}
let last=[high..high] let empty=[high..high)
let c=[loop x in last x] let d=[loop x in empty x]
return if count =? 3 and a =? [low high] and b =? [high low] and c =? [high] and d.length =? 0
and low in? all and high in? all and 0 in? all and 0 notin? wide 42 else 1
}''',
    'stored-range-capture': '''let order:int64=0
bound=(tag:int64 value:int64)=>{order=order*10+tag return value}
main=()=>{
let end:int64=8
let r=[bound(1 0),bound(2 2)..bound(3 end))
end=100
let saved=r let values:array<int64>=[]
loop x in r {r=[100..101] if x =? 2 continue values.push(x)}
return if order =? 123 and values =? [0 4 6] and 4 in? saved and 4 notin? r 42 else 1
}''',
    'stored-range-membership-order': '''let r=[0..2]
needle=()=>{r=[20..22] return 21}
main=()=>{
let found=needle() in? r
return if found 42 else 1
}''',
    'stored-range-membership-endpoints': '''let order:int64=0
bound=(tag:int64 value:int64)=>{order=order*10+tag return value}
main=()=>{
let found=bound(1 4) in? [bound(2 0),bound(3 2)..bound(4 8))
return if found and order =? 1234 42 else 1
}''',
    'stored-range-no-allocation': '''sum=(end:int64)=>{
let r=[1,3..end) let total:int64=0 loop x in r {total+=x}
return total
}
main=()=>{
sum(1000) let before=alloc_count()
let result=sum(1000)
return if result =? 250000 and alloc_count() =? before 42 else 1
}''',
    'stored-range-combined': '''main=()=>{
let r=[1,3..7] let sum:int64=0 let count:int64=0
loop x in r and y in [10 20] {sum+=x+y}
loop x in r or y in [10] {count+=1}
let nested:int64=0 loop x in r {loop y in r {nested+=1}}
return if sum =? 34 and count =? 4 and nested =? 16 42 else 1
}''',
    'stored-range-combined-literals': '''main=()=>{
let sum:int64=0 let count:int64=0
loop x in [1,3..7] and y in [10,20..30) {sum+=x+y}
loop x in [1,3..7] or y in [10,20..30) {count+=1}
return if sum =? 34 and count =? 4 42 else 1
}''',
    'stored-range-return': '''span=(first:int64 last:int64):>IntRange=>[first..last)
take=(r:IntRange)=>[loop x in r x]
main=()=>{
let record=[bounds=span(20 23)]
let ranges=[span(0 2) record.bounds]
return if take(ranges[0]) =? [0 1] and take(ranges[1]) =? [20 21 22] 42 else 1
}''',
    'stored-range-default': '''main=()=>{
let r:IntRange let values:array<IntRange>=[] values.resize(3)
let count:int64=0 loop x in r {count+=1}
loop item in values {loop x in item {count+=1} if 0 in? item return 1}
return if count =? 0 and 0 notin? r 42 else 2
}''',
    'answer': 'main=():>int64=>42',
    'rational-division-notation': '''main=()=>{
let sum=1/2+1/3
return if sum =? 5/6 and "{sum}" =? "5/6" and "{4/2}" =? "2"
and (-7)/3 =? -(7/3) and (2/3)^(-3) =? 27/8 42 else 1
}''',
    'rational-division-widths': '''divide=(a b)=>a/b
main=()=>{
if divide(7 as int8 -3 as int16) not=? (-7)/3 return 1
if divide(18446744073709551615 -1) not=? -18446744073709551615 return 2
if divide(-9223372036854775808 18446744073709551615) not=? (-9223372036854775808)/18446744073709551615 return 3
return if 123456789012345678901234567890/10 =? 12345678901234567890123456789
and 1/123456789012345678901234567890*123456789012345678901234567890 =? 1 42 else 4
}''',
    'rational-division-order': '''let order:int64=0
value=(n:int64)=>{order=order*10+n n}
main=()=>{let fraction=value(1)/value(2) return if order =? 12 and fraction =? 1/2 42 else 1}''',
    'rational-division-generic-mixed': '''divide=(a b)=>a/b
main=()=>if divide(3.0 2.0) =? 1.5 and divide(1 3) =? 1/3 42 else 1''',
    'rational-division-float': '''main=()=>{
let a:float32=3.0 let b:float32=2.0
return if a/b =? 1.5 and 3/2.0 =? 1.5 and 3.0/2 =? 1.5 42 else 1
}''',
    'rational-division-custom': '''BigInt:type=[value:int64]
__truediv__=(a:BigInt b:BigInt):>int64=>a.value//b.value
main=()=>BigInt[84]/BigInt[2]''',
    'rational-division-unused-constant': 'const unused=1/2\nmain=()=>42',
    'rational-float-usage': '''from bigint import bigint
main=()=>{
let step=(1/60).to_float32()
let position=vec2(step 2.0*step)
let huge:int64=1000
return if position.x >? 0.016 and position.x <? 0.017 and (1/2).to_float64() =? 0.5
and bigint(huge).to_float32() =? 1000.0 42 else 1
}''',
    'rational-float-lifetime': '''work=():>void=>{
let huge=123456789012345678901234567890
loop n in [1..20) {
let value=huge/(huge+n)
if value.to_float64() <? 0.99 or value.to_float32() <? 0.99 panic("lost ratio")
if huge.to_float64() <? 1e20 or huge.to_float32() <? 1e20 panic("lost integer")
}
}
main=()=>{work() let before=alloc_count() loop i in [0..20) {work()}
return if alloc_count() =? before 42 else 1}''',
    'rational-division-lifetime': '''work=():>void=>{
let fractions=[1/2 2/3 3/4] let copy=fractions
fractions[0]=5/6
if copy[0] not=? 1/2 panic("lost value copy")
loop n in [1..15) {let ratio=n/(n+1) let text="{ratio}" if text.length =? 0 panic("missing fraction")}
}
main=()=>{work() let before=alloc_count() loop i in [0..20) {work()}
return if alloc_count() =? before 42 else 1}''',
    'floor-literal-inference': '''check=(a)=>{let q=a//2 let r=a%3 return q-100 =? -58 and r-100 =? -99}
main=()=>if check(85) and check(85 as int8) and check(85 as int16) and check(85 as int32)
and check(85 as uint8) and check(85 as uint16) and check(85 as uint32) 42 else 1''',
    'syntax-coefficients': '''twice=(x:int64)=>2x
main=()=>{let x:int64=19 return twice(x)+2(x-17)}''',
    'syntax-coefficient-call': '''value=()=>21
main=()=>2value()''',
    'syntax-coefficient-exponent-name': 'main=()=>{let energy:int64=21 return 2energy}',
    'syntax-coefficient-e': '''main=()=>{let e:float64=2.0
return if 2e + 1e1 =? 14.0 42 else 1}''',
    'syntax-multiline': '''Choice:type=int64
    | string
main=()=>if 1 =? 1
    and 2 =? 2 {
    let x:int64=40
        + 2
    return x
} else 1''',
    'syntax-nested-interpolation': '''main=()=>{let café:int64=42
let text="result {\"{café}\"}"
return if text =? "result 42" 42 else 1}''',
    'syntax-separated-negative-elements': '''main=()=>{let xs:array<int64>=[40
-2
4] return xs[0]+xs[1]+xs[2]}''',
    'calls': 'add=(a:int64 b:int64):>int64=>a+b\nmain=():>int64=>add(20 22)',
    'inferred-function': 'twice=(x)=>x*2\nmain=()=>twice(21)',
    'optimizer-select-arithmetic': """choose=(x:int64):>int64=>if x%2 =? 0 x//2 else 3*x+1
main=()=>{let total:int64=0
loop x in [0..100) total+=choose(x)
return if total=?8775 and choose(-3)=?(-8) and choose(-4)=?(-2) 42 else 1}""",
    'optimizer-select-widths': """signed=(take:bool a:int8 b:int8):>int8=>if take a+1 else b-1
unsigned=(take:bool a:uint64 b:uint64):>uint64=>if take a xor b else a+b
main=()=>{let high:uint64=18446744073709551615
return if signed(true 127 0)=?(-128) and signed(false 0 (-128))=?127
and unsigned(true high 1)=?18446744073709551614 and unsigned(false high 1)=?0 42 else 1}""",
    'optimizer-select-lazy': """let calls:int64=0
bump=(n:int64):>int64=>{calls+=1 return n}
choose=(take:bool value:int64 divisor:int64 values:array<int64>):>int64=>
if take value+1 else value//divisor+values[10]
main=()=>{let a:int64=0 let b:int64=0
loop i in [0..10) {
a=if i%2 =? 0 {b+=1; a+1} else {b+=10; a+2}
let result=if i%2 =? 0 bump(20) else bump(22)
if result not=? (if i%2 =? 0 20 else 22) return 1
}
return if a=?15 and b=?55 and calls=?10 and choose(true 41 0 [])=?42 42 else 2}""",
    'optimizer-select-condition-order': """main=()=>{let x:int64=0 let total:int64=0
loop i in [0..10) {
let value=if {x+=1; x%2 =? 0} x*3 else x+1
total+=value
}
return if x=?10 and total=?120 42 else 1}""",
    'argument-borrow-global-write': '''let source:array<int64>=[20]
replace=():>void=>{source=[99]}
read=(value:array<int64>)=>{replace() return value[0]}
through=(@value:array<int64>)=>read(value)
main=()=>{source.push(1) let before=through(@source)
return if source[0]=?99 before+22 else 1}''',
    'argument-borrow-later-write': '''read=(value:array<int64> ignored:int64)=>value[0]
through=(@value:array<int64>)=>read(value {value=[99]; 0})
main=()=>{let source=[20] source.push(1) let before=through(@source)
return if source[0]=?99 before+22 else 1}''',
    'argument-borrow-callback-write': '''let source:array<int64>=[20]
read=(value:array<int64> callback:(():>void))=>{callback() return value[0]}
through=(@value:array<int64>)=>read(value ()=>{source=[99]})
main=()=>{source.push(1) let before=through(@source)
return if source[0]=?99 before+22 else 1}''',
    'argument-borrow-formatter-write': '''let source:array<int64>=[20]
Marker:type=[id:int64]
__fmt=(@buf:array<uint8> value:Marker):>void=>{source[0]=99 buf.push(120 as uint8)}
read=(value:array<int64>)=>{let text="{Marker[0]}" return value[0]}
through=(@value:array<int64>)=>read(value)
main=()=>{source.push(1) let before=through(@source)
return if source[0]=?99 before+22 else 1}''',
    'argument-borrow-later-formatter': '''let source:array<int64>=[20]
Marker:type=[id:int64]
__fmt=(@buf:array<uint8> value:Marker):>void=>{source[0]=99 buf.push(120 as uint8)}
read=(value:array<int64> ignored:string)=>value[0]
through=(@value:array<int64>)=>read(value "{Marker[0]}")
main=()=>{source.push(1) let before=through(@source)
return if source[0]=?99 before+22 else 1}''',
    'argument-borrow-nested-formatter': '''let source:array<int64>=[20]
Marker:type=[id:int64]
str=(value:Marker):>string=>{source[0]=99 return "x"}
read=(value:array<int64> ignored:string)=>value[0]
through=(@value:array<int64>)=>read(value "{[item=Marker[0]]}")
main=()=>{source.push(1) let before=through(@source)
return if source[0]=?99 before+22 else 1}''',
    'argument-mutable-field': """Item:type=[value:int64]
bump=(@value:int64):>void=>{value+=22}
main=()=>{let item=Item[20] let copy=item bump(@item.value)
return if copy.value=?20 item.value else 1}""",
    'argument-mutable-index': """bump=(@value:int64):>void=>{value+=22}
main=()=>{let values=[20 30] let copy=values let index:int64=0
bump(@values[index])
return if copy[0]=?20 and values[1]=?30 values[0] else 1}""",
    'argument-mutable-nested': """Item:type=[values:array<int64>]
bump=(@value:int64):>void=>{value+=22}
main=()=>{let items=[Item[[20 30]]] let copy=items let calls:int64=0
bump(@items[{calls+=1; 0}].values[0])
return if calls=?1 and copy[0].values[0]=?20 items[0].values[0] else 1}""",
    'optimizer-scalar-operand-values': '''main=()=>{
let x:int64=10
if x+{x=20; 3} not=? 13 return 1
x=10
if x-{x=20; 3} not=? 7 return 2
x=10
if x*{x=20; 3} not=? 30 return 3
x=10
if x//{x=20; 3} not=? 3 return 4
x=10
if x%{x=20; 3} not=? 1 return 5
x=10
if x<<{x=20; 1} not=? 20 return 6
x=10
if (x xor {x=20; 3}) not=? 9 return 7
x=10
if x <? {x=0; 5} return 8
x=10
if (x as uint64)+{x=20; 3} not=? 13 return 9
let small:int8=10
if small+{small=20; 3} not=? 13 return 10
let flag:bool=true
return if flag xor {flag=false; false} 42 else 11
}''',
    'optimizer-float-operand-values': '''main=()=>{
let x:float64=12.0
if x+{x=20.0; 3.0} not=? 15.0 return 1
x=12.0
if x-{x=20.0; 3.0} not=? 9.0 return 2
x=12.0
if x*{x=20.0; 3.0} not=? 36.0 return 3
x=12.0
if x/{x=20.0; 3.0} not=? 4.0 return 4
x=13.0
if x <? {x=0.0; 5.0} return 5
let single:float32=1.5
return if single+{single=2.5; 3.0} =? 4.5 42 else 6
}''',
    'optimizer-vector-operand-values': '''main=()=>{
let v=vec2(1 2)
let sum=v+{v=vec2(10 20); vec2(3 4)}
if sum not=? vec2(4 6) return 1
v=vec2(1 2)
let scaled=v*{v=vec2(10 20); 2.0}
if scaled not=? vec2(2 4) return 2
let factor:float32=2.0
let reverse=factor*{factor=10.0; vec2(3 4)}
if reverse not=? vec2(6 8) return 3
let iv=ivec2(1 2)
let integers=iv+{iv=ivec2(10 20); ivec2(3 4)}
return if integers =? ivec2(4 6) 42 else 4
}''',
    'optimizer-matrix-operand-values': '''main=()=>{
let matrix=mat4()
let product=matrix*{matrix=mat4(2); mat4()}
if product not=? mat4() return 1
matrix=mat4()
let point=matrix*{matrix=mat4(2); vec4(1 2 3 1)}
return if point =? vec4(1 2 3 1) 42 else 2
}''',
    'optimizer-short-circuit-scan': '''scan=(text:array<uint8>):>int64=>{
let i:int64=0 let total:int64=0
loop i <? text.length {
    if text[i] <? 48 or text[i] >? 57 {i+=1 continue}
    let value:int64=0
    loop i <? text.length and text[i] >=? 48 and text[i] <=? 57 {
        value=10*value+(text[i] as int64)-48 i+=1
    }
    total+=value
}
return total
}
main=()=>{return if scan(bytes("123 x 45 0 7")) =? 175 and scan(bytes("")) =? 0
and scan(bytes("1 20 300")) =? 321 and scan(bytes("no digits")) =? 0 42 else 1}''',
    'optimizer-conditional-loads': '''read=(take:bool values:array<int64>):>int64=>{
if take and values[0] >? 0 and values[0] <? 100 return values[0]
return 42
}
main=()=>{let empty:array<int64>=[]
if read(false empty) not=? 42 return 1
loop take in [true false] {
    let values=[7]
    let first=if take {let value=values[0] value*2} else 10
    if first not=? (if take 14 else 10) return 2
    if read(take values) not=? (if take 7 else 42) return 3
}
return 42}''',
    'optimizer-mutation-after-load': '''change=(@values:array<int64>):>bool=>{values[0]+=1 return true}
main=()=>{
let values=[7 11] let index:int64=0
if values[index] =? 7 and values[index] >? 0 {index=1}
if values[index] not=? 11 return 1
if values[0] =? 7 and change(@values) and values[0] =? 8 {values[0]=40}
if values[0] not=? 40 return 2
loop take in [true false] {
    if take and values[0] =? 40 {values[0]=41} else {values[0]=42}
}
return values[0]
}''',
    'optimizer-loop-loads': '''main=()=>{
let values=[1 2 3] let total:int64=0 let i:int64=0
loop i <? values.length {
    if values[i] >? 0 and values[i] <? 10 {total+=values[i]}
    values[i]+=10 i+=1
}
i=0
loop i <? values.length {total+=values[i] i+=1}
return total
}''',
    'optimizer-nested-loop-effects': '''main=()=>{
let integers=[0] let floats=[0.0] let history:array<int64>=[]
let counter:int64=0 let outer:int64=0
loop outer <? 4 {
    let before=integers[0] let before_float=floats[0] let before_length=history.length
    let before_counter=counter
    if false {loop unused in [0..3) {integers[0]=999 counter=999}}
    let inner:int64=0
    loop inner <? 3 {
        if inner =? 1 {inner+=1 continue}
        loop deepest in [0..2) {
            integers[0]+=outer+inner+deepest
            floats[0]+=0.5
            history.push(counter)
            counter+=1
        }
        inner+=1
    }
    if integers[0] not=? before+4*outer+6 return 1
    if floats[0] not=? before_float+2.0 return 2
    if history.length not=? before_length+4 or counter not=? before_counter+4 return 3
    loop sibling in [0..2) {integers[0]+=1 counter+=1}
    outer+=1
}
return if integers[0] =? 56 and floats[0] =? 8.0 and history.length =? 16 and counter =? 24 42 else 4
}''',
    'argument-array-numeric-context': '''unsigned=(values:array<uint64>)=>values[0]+values[1]
single=(values:array<float32>)=>values[0]+values[1]
octets=(values:array<uint8>)=>values[0]+values[1]
main=()=>{
let indirect:((values:array<uint64>):>uint64)=unsigned
return if unsigned([20 22]) =? 42 and single([20 22]) =? 42.0
and octets([20 22]) =? 42 and indirect([20 22]) =? 42 42 else 1
}''',
    'argument-array-nested-context': '''nested=(values:array<array<uint64>>)=>values[0][0]+values[1][0]
optional=(values:array<uint64>|none):>uint64=>if values is? none 0 else values[0]
main=()=>{
let nested_optional:array<array<uint64>>|none=[[42]]
return if nested([[20] [22]]) =? 42 and optional([42]) =? 42
and nested_optional is? array<array<uint64>> and nested_optional[0][0] =? 42 42 else 1
}''',
    'argument-array-overloads': '''pick = ((xs:array<int64>)=>1) & ((xs:array<uint64>)=>2) & ((xs:array<float64>)=>3)
main=()=>{return if pick([1 2]) =? 1 and pick([18446744073709551615]) =? 2
and pick([1.5 2.5]) =? 3 42 else 1}''',
    'argument-array-generic-context': '''first=<T>(values:array<T> seed:T):>T=>values[0]
plain=<T>(values:array<T>):>T=>values[0]
main=()=>{let seed:uint64=0
return if first([42] seed) =? 42 and first<float32>([42] 0) =? 42.0
and plain([42]) =? 42 and plain([[42]])[0] =? 42 42 else 1}''',
    'argument-array-order': '''let trace:int64=0
next=():>uint64=>{trace=trace*10+1 return 20}
last=():>uint64=>{trace=trace*10+2 return 22}
accept=(values:array<uint64> tail:uint64):>uint64=>values[0]+values[1]+tail
main=()=>{let result=accept([next() 0] last())
return if result =? 42 and trace =? 12 42 else 1}''',
    'argument-array-exact-records': '''from bigint import BigInt
Item:type=[values:array<uint64>]
exact=(values:array<BigInt>)=>values[0]+values[1]
items=(values:array<Item>)=>values[0].values[0]
main=()=>{return if exact([20 22]) =? 42 and items([[values=[42]]]) =? 42 42 else 1}''',
    'array-comparison-widths': '''main=()=>{
let wide:array<uint64>=[0 1 18446744073709551615]
let small:array<uint8>=[0 42 255] let signed:array<int8>=[-128 0 127]
let real:array<float32>=[1.25 2.5]
return if wide =? [0 1 18446744073709551615] and [0 1 18446744073709551615] =? wide
and small =? [0 42 255] and [0 42 255] =? small and small not=? [0 42]
and signed =? [-128 0 127] and [-128 0 127] =? signed
and real =? [1.25 2.5] and [1.25 2.5] =? real 42 else 1
}''',
    'array-comparison-nested-optional': '''main=()=>{
let matrix:array<array<uint8>>=[[1 2] [3]]
let present:array<uint16>|none=[1 2] let absent:array<uint16>|none=none
let empty:array<uint16>=[] let optional_empty:array<uint16>|none=[]
return if matrix =? [[1 2] [3]] and [[1 2] [3]] =? matrix
and present =? [1 2] and [1 2] =? present and absent not=? [1 2] and [1 2] not=? absent
and empty =? [] and [] =? empty and optional_empty =? [] and [] =? optional_empty 42 else 1
}''',
    'array-comparison-exact-records': '''from bigint import BigInt
Item:type=[amount:uint64]
main=()=>{
let exact:array<BigInt>=[0 123456789012345678901234567890]
let items:array<Item>=[[amount=42]]
return if exact =? [0 123456789012345678901234567890]
and [0 123456789012345678901234567890] =? exact
and items =? [[amount=42]] and [[amount=42]] =? items 42 else 1
}''',
    'array-comparison-order': '''let trace:int64=0
value=(tag:int64):>uint64=>{trace=trace*10+tag return 42}
make_array=(tag:int64):>array<uint64>=>{trace=trace*10+tag return [42]}
main=()=>{
if [value(1)] not=? make_array(2) or trace not=? 12 return 1
trace=0
if make_array(1) not=? [value(2)] or trace not=? 12 return 2
return 42
}''',
    'array-comparison-record-snapshots': '''Item:type=[amount:int64]
change=(@item:Item):>Item=>{item.amount=2 return [amount=1]}
main=()=>{
let item:Item=[amount=1]
if item not=? change(@item) or item.amount not=? 2 return 1
let nested=[values=[1 2]]
if nested.values not=? {nested.values.clear() [1 2]} or nested.values.length not=? 0 return 2
let values=[1 2]
if values not=? {values=[3 4] [1 2]} or values[0] not=? 3 return 3
return 42
}''',
    'array-comparison-concat-snapshots': '''main=()=>{
let text="a"
let joined=text+{text="b"; "c"}
if joined not=? "ac" or text not=? "b" return 1
text="a"
if text not=? {text="b"; "a"} return 2
let values=[1]
let combined=values+{values=[2]; [3]}
return if combined =? [1 3] and values =? [2] 42 else 3
}''',
    'array-comparison-snapshots': '''change=(@values:array<uint64>):>uint64=>{values[0]=2 return 1}
main=()=>{
let values:array<uint64>=[1]
if values not=? [change(@values)] or values[0] not=? 2 return 1
values[0]=1
if [change(@values)] =? values or values[0] not=? 2 return 2
return 42
}''',
    'power-precedence': '''main=()=>{
if 2^3^2 not=? 512 or (2^3)^2 not=? 64 return 1
if -2^2 not=? -4 or (-2)^2 not=? 4 return 2
let x:int64=3
return if 2x^2 =? 18 and 2*3^2 =? 18 and 2^3*2 =? 16 and 0^0 =? 1 42 else 3
}''',
    'power-unsigned': '''main=()=>{
let value:uint64=18446744073709551615
if value^2 not=? 1 or value^3 not=? value return 1
if 18446744073709551615^1 not=? value return 2
return if (2 as uint64)^63 =? 9223372036854775808 and value^0 =? 1 42 else 3
}''',
    'power-floating': '''main=()=>{
let a:float64=2.0^(-3.0) let b:float32=(2.0 as float32)^(3.0 as float32)
return if abs(a-0.125) <? 0.000001 and abs(b-8.0) <? 0.0001 and abs(9.0^0.5-3.0) <? 0.000001 42 else 1
}''',
    'power-exact': '''from bigint import bigint
from rational import rational
main=()=>{
if bigint(2)^100 not=? bigint("1267650600228229401496703205376") return 1
if rational(2 3)^(-3) not=? rational(27 8) return 2
return if bigint(2)^3^2 =? 512 and rational(0)^0 =? 1 42 else 3
}''',
    'power-custom-order': '''Box:type=[value:int64]
let trace:string=""
base=()=>{trace+="a" return Box[40]}
exponent=()=>{trace+="b" return 2}
__pow__=(base:Box exponent:int64)=>Box[base.value+exponent]
__xor__=(a:Box b:Box)=>Box[a.value xor b.value]
main=()=>{let answer=base()^exponent()
return if answer.value =? 42 and trace =? "ab" and (Box[40] xor Box[2]).value =? 42 42 else 1}
''',
    'rational-parse': '''from rational import rational, parse_rational, Rational
main=()=>{
loop text in ["" "+" "-" "1/" "/2" "1/0" "1/2/3" " 1" "1 /2" "1.5" "１２"] {
    if parse_rational(text) isnt? none return 1
}
let half=rational("-0002/-0004")
if "{half}" not=? "1/2" or "{rational(0 -3)}" not=? "0" return 2
return if half =? rational("1" "2") and Rational[] =? 0 and rational("+42") =? 42 42 else 3
}''',
    'rational-mixed': '''from rational import rational
from bigint import bigint
main=()=>{
let half=rational(1 2) let wide:uint64=18446744073709551615
if half+2 not=? 2+half or half+bigint(2) not=? rational(5 2) return 1
if half+wide not=? rational("36893488147419103231" "2") return 2
if wide-half not=? rational("36893488147419103229" "2") return 3
if half*wide not=? wide*half or 2/half not=? 4 or half/2 not=? rational(1 4) return 4
if half//2 not=? 0 or 2//half not=? 4 or half%2 not=? half or 2%half not=? 0 return 5
return if half <? 1 and 0 <? half and half >=? half and half <=? half and 1 >? half 42 else 6
}''',
    'rational-powers': '''from rational import rational
main=()=>{
if rational(-2 3).pow(-3) not=? rational(-27 8) return 1
if rational(-2 3).pow(4) not=? rational(16 81) return 2
if rational(0).pow(0) not=? 1 or rational(0).pow(7) not=? 0 return 3
if rational(1).pow(-9223372036854775808) not=? 1 return 4
if rational(-1).pow(-9223372036854775808) not=? 1 return 5
if rational(-1).pow(9223372036854775807) not=? -1 return 6
return if rational(-7 3).floor() =? -3 and rational(-7 3).ceil() =? -2
    and rational(7 3).floor() =? 2 and rational(7 3).ceil() =? 3 42 else 7
}''',
    'rational-copies-and-keys': '''from rational import rational
main=()=>{
let a=rational(2 3) let b=a let values=[a a]
values[0]+=1 values[1]*=2
if a not=? b or values[0] not=? rational(5 3) or values[1] not=? rational(4 3) return 1
let keys=[a->42 rational(0)->1]
return if keys[rational(-4 -6)] =? 42 and keys[rational(0 -17)] =? 1 42 else 2
}''',
    'rational-lifetime': '''from rational import rational
work=():>void=>{
let a=rational("123456789012345678901234567890" "9876543210123456789")
loop i in [1..12) {let value=(a+i)/rational(i 3) let parts=value.divmod(rational(2 7))
let text="{parts.remainder}" if text.length =? 0 panic("missing fraction")}
}
main=()=>{work() let before=alloc_count() loop i in [0..20) {work()}
return if alloc_count() =? before 42 else 1}''',
    'bigint-literal-auto-import': '''main=()=>{
let value=123456789012345678901234567890
return if "{value+42}" =? "123456789012345678901234567932"
and value//10 =? 12345678901234567890123456789 and value%10 =? 0 42 else 1
}''',
    'bigint-literal-negative': '''main=()=>{
let values=[-9223372036854775809 -18446744073709551615 -18446744073709551616 -123456789012345678901234567890]
if values[0]+9223372036854775807 not=? -2 return 1
if values[1]+18446744073709551615 not=? 0 return 2
if values[2]+18446744073709551615 not=? -1 return 3
return if -values[3] =? 123456789012345678901234567890 42 else 4
}''',
    'bigint-literal-context': '''from bigint import BigInt, bigint
read=(value:BigInt=42):>BigInt=>value
main=()=>{
let values:array<BigInt>=[0 42 -9223372036854775808 18446744073709551615]
let inferred=[1 -2 123456789012345678901234567890]
let optional:BigInt|none=42
if optional is? none return 1
if values[0] not=? 0 or values[1] not=? 42 or values[2].to_int64() not=? -9223372036854775808 return 2
if values[3].to_uint64() not=? 18446744073709551615 or inferred[1] not=? -2 return 3
return if optional =? 42 and read() =? 42 and read(7) =? 7 and bigint(inferred[2]) =? inferred[2] 42 else 4
}''',
    'bigint-literal-record-and-map': '''from bigint import BigInt
Record:type=[value:BigInt=42]
main=()=>{
let row=Record[] let data:dict<BigInt string>=[0->"zero" 42->"answer" 123456789012345678901234567890->"large"]
let copy=data data[42]="changed"
return if row.value =? 42 and data[0] =? "zero" and copy[42] =? "answer"
and data[123456789012345678901234567890] =? "large" 42 else 1
}''',
    'bigint-literal-lifetime': '''work=():>void=>{
let values=[1 2 123456789012345678901234567890]
loop i in [0..10) {let text="{values[2]+i}" if text.length <? 30 panic("lost digits")}
}
main=()=>{work() let before=alloc_count() loop i in [0..30) {work()}
return if alloc_count() =? before 42 else 1}''',
    'bigint-literal-defaults': '''let calls:int64=0
make=()=>{calls=calls+1 123456789012345678901234567890}
read=(value=123456789012345678901234567890)=>value
called=(value=make())=>value
main=()=>{
if read() not=? called() or calls not=? 1 return 1
if called(42) not=? 42 or calls not=? 1 return 2
return if called() =? read() and calls =? 2 42 else 3
}''',
    'bigint-literal-overload': '''from bigint import BigInt
choose=((value:int64)=>1)&((value:uint64)=>2)&((value:BigInt)=>3)
main=()=>if choose(42) =? 1 and choose(18446744073709551615) =? 2
and choose(18446744073709551616) =? 3 and choose(-9223372036854775809) =? 3 42 else 1''',
    'bigint-bitwise-mixed': '''from bigint import bigint
main=()=>{
let a=18446744073709551616 let signed:int64=-1 let word:uint64=18446744073709551615
let saved=a
if (a and signed) not=? a or (signed and a) not=? a return 1
if (a or word) not=? 36893488147419103231 or (word or a) not=? 36893488147419103231 return 2
if (a xor signed) not=? -18446744073709551617 or (signed xor a) not=? -18446744073709551617 return 3
if (a and word) not=? 0 or (word and a) not=? 0 return 4
if (a or signed) not=? -1 or (signed or a) not=? -1 return 5
if (a xor word) not=? 36893488147419103231 or (word xor a) not=? 36893488147419103231 return 6
a<<=17 a>>=17
if a not=? saved or (not a) not=? -18446744073709551617 return 7
let huge:int64=9223372036854775807
return if (a >> huge) =? 0 and ((-a) >> huge) =? -1 and (bigint(0) << huge) =? 0 42 else 8
}''',
    'bigint-shift-places': '''from bigint import BigInt, bigint
let calls:int64=0
next=():>int64=>{calls+=1 return 0}
main=()=>{
let pool:Pool<array<BigInt>>=[] let h=pool.add([bigint(2)]) let saved=pool
pool[h][next()]<<=3 pool[h][0]>>=2
let words=[21] words[next()]<<=2 words[0]>>=1
return if calls =? 2 and pool[h][0] =? 4 and saved[h][0] =? 2 and words[0] =? 42 42 else 1
}''',
    'bigint-bitwise-lifetime': '''from bigint import bigint
exercise=():>void=>{
let a=123456789012345678901234567890 let b=-98765432109876543210987654321
let saved=a
loop i in [0..20) {
    let shifted=a << i
    let mixed=(a and b) or (a xor b)
    if (shifted >> i) not=? saved or mixed not=? (a or b) panic("bit operation mismatch")
    a=not (not a)
}
}
main=()=>{exercise() let before=alloc_count() exercise()
return if before =? alloc_count() 42 else 1}''',
    'generic-operator-bits': '''Flags:type=[bits:uint64]
let order:int64=0
make=(tag:int64 bits:uint64):>Flags=>{order=order*10+tag return Flags[bits]}
__and__=(a:Flags b:Flags):>Flags=>Flags[a.bits and b.bits]
__or__=(a:Flags b:Flags):>Flags=>Flags[a.bits or b.bits]
__xor__=(a:Flags b:Flags):>Flags=>Flags[a.bits xor b.bits]
__not__=(a:Flags):>Flags=>Flags[not a.bits]
main=()=>{
let joined=make(1 3) or make(2 4)
let common=make(3 7) and make(4 2)
let flipped=joined xor common
return if order =? 1234 and joined.bits =? 7 and common.bits =? 2
and flipped.bits =? 5 and (not flipped).bits =? 18446744073709551610 42 else 1
}''',
    'bigint-parse': '''from bigint import bigint, parse_bigint
main=()=>{
loop text in ["" "+" "-" " 1" "1 " "1_0" "1.0" "🙂" "１２"] {if parse_bigint(text) isnt? none return 1}
let zero=bigint("-0000") let positive=bigint("+00042") let negative=bigint("-00042")
return if "{zero}" =? "0" and "{positive}" =? "42" and "{negative}" =? "-42" and zero.gcd(zero) =? 0 42 else 2
}''',
    'bigint-conversions': '''from bigint import bigint
main=()=>{
if bigint(-9223372036854775808).to_int64() not=? -9223372036854775808 return 1
if bigint(9223372036854775807).to_int64() not=? 9223372036854775807 return 2
if bigint(18446744073709551615).to_uint64() not=? 18446744073709551615 return 3
if bigint("9223372036854775808").to_int64() isnt? none return 4
if bigint("-9223372036854775809").to_int64() isnt? none return 5
if bigint("18446744073709551616").to_uint64() isnt? none return 6
if bigint(-1).to_uint64() isnt? none return 7
return if bigint(0).to_int64() =? 0 and bigint(0).to_uint64() =? 0 42 else 8
}''',
    'bigint-powers': '''from bigint import bigint
main=()=>{
let large=bigint(2).pow(100)
if "{large}" not=? "1267650600228229401496703205376" return 1
if "{bigint(-3).pow(101)}" not=? "-1546132562196033993109383389296863818106322566003" return 2
return if bigint(0).pow(0) =? 1 and bigint(0).pow(10) =? 0 and bigint(-1).pow(21) =? -1 42 else 3
}''',
    'bigint-mixed-and-copies': '''from bigint import bigint
main=()=>{
let value=bigint("123456789012345678901234567890") let copy=value
let values=[value value] values[0]+=42 values[1]*=2
if values[0]-42 not=? value or values[1]//2 not=? value or copy not=? value return 1
let wide:uint64=18446744073709551615
if value+wide not=? wide+value or value*wide not=? wide*value return 2
if (wide-value)+value not=? wide or value+(-7) not=? -7+value return 3
if not (7 <? value) or not (value >? 7) or not (value >=? value) return 4
return if "{value}" =? "123456789012345678901234567890" 42 else 5
}''',
    'bigint-map-keys': '''from bigint import bigint
main=()=>{let keys=[bigint("12345678901234567890")->42 bigint(0)->1]
let another=bigint("12345678901234567889")+1
return if keys[another] =? 42 and keys[bigint("-000")] =? 1 42 else 1}''',
    'bigint-lifetime': '''from bigint import bigint
work=():>void=>{
let original=bigint("123456789012345678901234567890")
loop i in [1..12) {let value=(original+i)*3 let parts=value.divmod(bigint(i+1))
let text="{parts.quotient}" if text.length =? 0 panic("missing digits")}
}
main=()=>{work() let before=alloc_count() loop i in [0..40) {work()}
return if alloc_count() =? before 42 else 1}''',
    'bigint-literal-floor': '''from bigint import bigint
main=()=>{let value=bigint("123456789012345678901234567891")
if "{value//2}" not=? "61728394506172839450617283945" or value%2 not=? 1 return 1
if "{(-value)//2}" not=? "-61728394506172839450617283946" or (-value)%2 not=? 1 return 2
return if value//1 =? value and value%1 =? 0 and value%8 =? 3 42 else 3}''',
    'overload-group-unsigned-literal': '''choose=((value:int64)=>1)&((value:uint64)=>42)
main=()=>if choose(42) =? 1 choose(18446744073709551615) else 2''',
    'generic-operator-floor': '''Box:type=[value:int64]
__floordiv__=(a:Box b:int64)=>Box[a.value+b]
__mod__=(a:Box b:int64)=>Box[a.value+b]
main=()=>{let box=Box[40] let a=box//2 let b=box%8
return if a.value =? 42 and b.value =? 48 42 else 1}''',
    'overload-group-arity': '''let choose = (():>int64=>40) & ((value:int64):>int64=>value+2)
main=()=>choose()+choose(0)''',
    'overload-group-types': '''const measure = (((value:int64)=>value) & ((text:string)=>text.length))
main=()=>measure(40)+measure("ab")''',
    'overload-group-generic': '''first = (<T>(items:array<T>):>T=>items[0]) & ((value:int64)=>value)
main=()=>{let word=first<string>(["hello" "world"])
return if word =? "hello" first([40 1])+first(2) else 1}''',
    'overload-group-defaults': '''choose = ((x:int64 y:int64=x+2)=>x+y) & ((text:string)=>text.length)
main=()=>if choose(text="ab") =? 2 choose(x=20) else 1''',
    'overload-group-callable': '''step = ((value:int64):>int64=>value+2) & ((value:string):>string=>value+"!")
apply=(f:((value:int64):>int64) value:int64):>int64=>f(value)
main=()=>apply(step 40)''',
    'overload-group-operators': '''Point:type=[x:int64 y:int64]
__mul__ = ((v:Point amount:int64)=>Point[v.x*amount v.y*amount])
        & ((amount:int64 v:Point)=>Point[amount*v.x amount*v.y])
main=()=>{let point=Point[10 11] let a=point*2 let b=2point
return if a =? b a.x+a.y else 1}''',
    'overload-group-recursion': '''sum = (():>int64=>0)
    & ((n:int64):>int64=>if n =? 0 sum() else n+sum(n-1))
main=()=>sum(8)+sum(3)''',
    'overload-group-parenthesized': 'main=(():>int64=>42)',
    'generic-records': '''Box:type=<T>[value:T history:array<T>=[]]
Pair:type=<A B>[left:A right:B]
Words:type=Box<array<string>>
Values:type=<T>(array<T>)
Container:type=<T>(Box<Values<T>>)
let global:Box<int64>=[value=42]
main=()=>{
    let a=Box<string>["hello"] let b:Box<int64>=[value=20]
    let pair=Pair<Box<string> Box<int64>>[a b]
    let words:Words=[value=["one" "two"]]
    let copy=words words.value[0]="changed"
    let inferred=Box(22)
    let aliased=Container<string>[value=["aliased"]]
    let values:Values<int64>=[42]
    if aliased.value[0] not=? "aliased" or values[0] not=? 42 return 2
    return if pair.left.value =? "hello" and copy.value[0] =? "one" and words.history.length =? 0
        and pair.right.value+inferred.value =? 42 and global.value =? 42 42 else 1
}''',
    'generic-typed-functions': '''first=<T>(xs:array<T>):>T|none=>if xs.length >? 0 xs[0] else none
identity=<T>(x:T):>T=>x
empty=<T>():>array<T>=>[]
combine=<T>(a:T b:T=a):>T=>a+b
count_down=<T>(n:T acc:T):>T=>if n <=? 0 acc else count_down(n-1 acc+n)
main=()=>{
    let a=first([42 10]) let b=first(["yes"])
    let items=identity<array<dict<string int64>>>([["answer"->42]])
    let no_values=empty<string>()
    let typed:((x:int64):>int64)=identity
    return if a =? 42 and b =? "yes" and items[0]["answer"] =? 42 and no_values.length =? 0
        and typed(42) =? 42 and combine(21) =? 42 and combine<string>(b="b" a="a") =? "ab"
        and count_down(4 0) =? 10 42 else 1
}''',
    'generic-library-containers': '''Enemy:type=[name:string health:int64]
main=()=>{
    let enemies:Pool<Enemy>=[]
    let first=enemies.add(Enemy["one" 42]) let second=enemies.add(Enemy["two" 20])
    let copy=enemies
    enemies[first].health-=10
    if copy[first].health not=? 42 or enemies[first].health not=? 32 return 1
    if not enemies.remove(first) or enemies.has(first) or not enemies.has(second) return 2
    let third=enemies.add(Enemy["three" 30])
    if enemies.has(first) or enemies[second].name not=? "two" or enemies[third].health not=? 30 return 3
    let removed=enemies.get(first)
    if removed isnt? none return 4
    let pending:Heap<string>=[]
    pending.push("later" 2.0) pending.push("first" 1.0)
    let saved=pending
    if pending.pop() not=? "first" or pending.pop() not=? "later" or saved.peek() not=? "first" return 5
    let arrays:Pool<array<string>>=[] let handle=arrays.add(["hello"])
    let original=arrays let updated=arrays[handle] updated[0]="changed" arrays[handle]=updated
    return if original[handle][0] =? "hello" and arrays[handle][0] =? "changed" 42 else 6
}''',
    'generic-index-parameter-copy': '''edit=(pool:Pool<array<int64>> handle:Handle)=>{pool[handle][0]=42 return pool[handle][0]}
main=()=>{let p:Pool<array<int64>>=[] let h=p.add([1])
return if edit(p h) =? 42 and p[h][0] =? 1 42 else 1}''',
    'generic-operator-arithmetic': '''Vec:type=[x:int64 y:int64]
__add__=(a:Vec b:Vec)=>Vec[a.x+b.x a.y+b.y]
__sub__=(a:Vec b:Vec)=>Vec[a.x-b.x a.y-b.y]
__mul__=(a:Vec b:int64)=>Vec[a.x*b a.y*b]
__mul__=(a:int64 b:Vec)=>Vec[a*b.x a*b.y]
__unary_sub__=(a:Vec)=>Vec[-a.x -a.y]
main=()=>{let a=Vec[10 11] let b=Vec[1 2]
let total=2a+2b-2b let negative=-total
return if negative.x =? -20 and negative.y =? -22 and __add__(a a) =? total 42 else 1}''',
    'generic-operator-comparison': '''Score:type=[value:int64 label:string]
__eq__=(a:Score b:Score)=>a.value =? b.value
__lt__=(a:Score b:Score)=>a.value <? b.value
main=()=>{let a=Score[1 "a"] let b=Score[2 "b"] let same=Score[1 "different"]
return if a =? same and a not=? b and a <? b and b >? a and a <=? same and same >=? a 42 else 1}''',
    'generic-operator-source-order': '''Score:type=[value:int64]
trace=""
mark=(label:string value:int64)=>{trace+=label return Score[value]}
__lt__=(a:Score b:Score)=>a.value <? b.value
main=()=>{
if not (mark("a" 42) >? mark("b" 20)) return 1
if not (mark("c" 20) <=? mark("d" 42)) return 2
if not (mark("e" 42) >=? mark("f" 20)) return 3
return if trace =? "abcdef" 42 else 4}''',
    'generic-operator-specialization': '''Box:type=<T>[value:T]
__add__=<T>(a:Box<T> b:Box<T>):>Box<T>=>Box<T>[a.value+b.value]
main=()=>{let number=Box<int64>[20]+Box<int64>[22] let text=Box<string>["hello"]+Box<string>["!"]
return if number.value =? 42 and text.value =? "hello!" 42 else 1}''',
    'generic-operator-index': '''Store:type=<T>[values:array<T>]
__index__=<T>(s:Store<T> i:int64):>T=>s.values[i]
__setindex__=<T>(@s:Store<T> i:int64 value:T):>void=>{s.values[i]=value}
main=()=>{let s=Store<array<int64>>[[[20 22]]] let old=s
s[0][1]+=20 s[0][0]=42
return if s[0] =? [42 42] and old[0] =? [20 22] 42 else 1}''',
    'generic-index-array': '''main=()=>{
let pool:Pool<array<int64>>=[] let handle=pool.add([20 22]) let original=pool
pool[handle][0]=42 pool[handle][1]+=20
return if pool[handle] =? [42 42] and original[handle] =? [20 22] 42 else 1}''',
    'generic-index-field-array': '''Item:type=[values:array<[amount:int64]>]
main=()=>{
let pool:Pool<Item>=[] let h=pool.add(Item[[[amount=20] [amount=22]]]) let original=pool
pool[h].values[1].amount+=20
return if pool[h].values[1].amount =? 42 and original[h].values[1].amount =? 22 42 else 1}''',
    'generic-index-nested-pools': '''main=()=>{
let inner:Pool<array<int64>>=[] let a=inner.add([20 22])
let outer:Pool<Pool<array<int64>>>=[] let b=outer.add(inner) let original=outer
outer[b][a][0]=42
return if outer[b][a][0] =? 42 and original[b][a][0] =? 20 and inner[a][0] =? 20 42 else 1}''',
    'generic-index-array-and-map': '''main=()=>{
let pool:Pool<array<int64>>=[] let h=pool.add([20])
let array=[pool] let map=["entry"->pool]
array[0][h][0]=42 map["entry"][h][0]+=22
return if array[0][h][0] =? 42 and map["entry"][h][0] =? 42 and pool[h][0] =? 20 42 else 1}''',
    'generic-pool-direct-snapshots': '''Item:type=[values:array<int64> health:int64=10]
main=()=>{
let original_values=[20 22] let pool:Pool<Item>=[]
let a=pool.add(Item[original_values]) let b=pool.add(Item[original_values])
let snapshot=pool let delta:int64=2
pool[a].values[0]+=delta pool[b].values[1]=40 pool[a].health-=delta
let pools=[pool] let at:int64=0
pools[at][a].values[0]=42
return if original_values =? [20 22] and snapshot[a].values =? [20 22]
and snapshot[b].values =? [20 22] and pool[a].values =? [22 22]
and pool[b].values =? [20 40] and pool[a].health =? 8
and pools[0][a].values =? [42 22] 42 else 1
}''',
    'generic-pool-direct-expressions': '''Item:type=[values:array<int64> speed:float32 active:bool]
main=()=>{
let pool:Pool<Item>=[] let h=pool.add(Item[[20 22] 2.0 false]) let saved=pool
let slot:int64=0 let delta:int64=3 let factor:float32=4.0
pool[h].values[slot+1]+=delta*7-1
pool[h].values[-slot]=-(delta-23)
pool[h].speed+=factor*(delta as float32)
pool[h].active=not (delta <? 0) and (slot =? 0 or delta <? 0)
return if pool[h].values =? [20 42] and pool[h].speed =? 14.0 and pool[h].active
and saved[h].values =? [20 22] and saved[h].speed =? 2.0 and not saved[h].active 42 else 1
}''',
    'generic-pool-direct-expression-effects': '''Item:type=[values:array<int64> health:int64=10]
Amount:type=[value:int64]
let pool:Pool<Item>=[] let h:Handle=[]
__add__=(a:Amount b:Amount):>int64=>{pool[h].health=99 return a.value+b.value}
main=()=>{h=pool.add(Item[[20]]) let a=Amount[10] let b=Amount[11]
pool[h].values[0]+=1+(a+b)
return if pool[h].values[0] =? 42 and pool[h].health =? 10 42 else 1}
''',
    'generic-pool-direct-short-circuit': '''Item:type=[active:bool health:int64=10]
let pool:Pool<Item>=[] let h:Handle=[] let calls:int64=0
touch=():>bool=>{calls+=1 pool[h].health=99 return true}
main=()=>{h=pool.add(Item[false]) let yes=true let no=false
pool[h].active=yes or touch()
pool[h].active=no and touch()
if calls not=? 0 return 1
pool[h].active=no or touch()
return if calls =? 1 and pool[h].active and pool[h].health =? 10 42 else 1}
''',
    'generic-pool-direct-helper-shadow': '''main=()=>{
let __pool_index=(p:Pool<array<int64>> h:Handle):>int64=>1
let pool:Pool<array<int64>>=[] let a=pool.add([20]) let b=pool.add([30])
pool[a][0]=42
return if pool[a][0] =? 42 and pool[b][0] =? 30 and __pool_index(pool a) =? 1 42 else 1
}''',
    'generic-pool-direct-custom-setter': '''let writes:int64=0
__setindex__=(@pool:Pool<array<int64>> h:Handle value:array<int64>):>void=>{
writes+=1 pool.items[pool.index_of(h)]=value
}
main=()=>{let pool:Pool<array<int64>>=[] let h=pool.add([20])
pool[h][0]+=22
return if pool[h][0] =? 42 and writes =? 1 42 else 1}''',
    'generic-pool-direct-side-effects': '''Item:type=[values:array<int64> health:int64=10]
let pool:Pool<Item>=[] let handle:Handle=[] let other:Handle=[]
change=():>int64=>{pool[handle].health=99 handle=other return 22}
main=()=>{let first=pool.add(Item[[20]]) other=pool.add(Item[[1]]) handle=first
pool[handle].values[0]+=change()
return if pool[first].values[0] =? 42 and pool[first].health =? 10
and pool[other].values[0] =? 1 and handle =? other 42 else 1}''',
    'generic-pool-direct-custom-getter': '''let reads:int64=0
__index__=(pool:Pool<array<int64>> h:Handle):>array<int64>=>{
reads+=1 return pool.items[pool.index_of(h)]
}
main=()=>{let pool:Pool<array<int64>>=[] let h=pool.add([20])
pool[h][0]+=22
return if reads =? 1 and pool.items[0][0] =? 42 42 else 1}''',
    'generic-pool-direct-impostor': '''Pool:type=<T>[items:array<T>]
let writes:int64=0
__index__=<T>(p:Pool<T> i:int64):>T=>p.items[i]
__setindex__=<T>(@p:Pool<T> i:int64 value:T):>void=>{writes+=1 p.items[i]=value}
main=()=>{let pool=Pool<array<int64>>[[[20]]]
pool[0][0]+=22 return if writes =? 1 and pool.items[0][0] =? 42 42 else 1}''',
    'generic-pool-direct-lifetime': '''Item:type=[values:array<int64>]
exercise=():>void=>{let pool:Pool<Item>=[] let h=pool.add(Item[[1 2 3]])
let saved=pool
loop i in [0..20) {pool[h].values[0]+=1 pool[h].values[1]=i}
if saved[h].values not=? [1 2 3] panic("snapshot changed")
}
main=()=>{exercise() let before=alloc_count()
loop i in [0..20) {exercise()}
return if alloc_count() =? before 42 else 1}''',
    'generic-type-defaults': '''empty=<T>():>array<T>=>[]
fallback=<T>(values:array<T>=empty<T>()):>array<T>=>values
Bucket:type=<T>[values:array<T>=empty<T>()]
main=()=>{let one=fallback<int64>() let two=Bucket<string>[] let three:Bucket<int64>
return if one.length =? 0 and two.values.length =? 0 and three.values.length =? 0 42 else 1}''',
    'generic-return-closure': '''keep=<T>(value:T):>(():>T)=>()=>value
main=()=>{let original=[42] let retained=keep(original) original[0]=1
let value=retained() value[0]=3 return if retained()[0] =? 42 and original[0] =? 1 42 else 1}''',
    'generic-structural-result': '''swap=<T U>(a:T b:U):>[x:U y:T]=>[x=b y=a]
main=()=>{let result=swap(42 "hello") return if result.x =? "hello" and result.y =? 42 42 else 1}''',
    'generic-function': '''twice=(x)=>x+x
main=()=>if twice(21) =? 42 and twice(1.25) =? 2.5 42 else 1''',
    'default-argument': 'add=(x y=2)=>x+y\nmain=()=>add(40)',
    'default-reference-call': '''let count:int64=0
next=()=>{count+=1 return 21}
combine=(a:int64 b:int64=a)=>a+b
main=()=>{let result=combine(next()) return if count =? 1 result else 1}''',
    'default-reference-snapshot': '''combine=(a:int64 b:int64 c:int64=a)=>a+c+b
main=()=>{let x:int64=21 return combine(x {x=99 0})}''',
    'default-reference-chain': '''let count:int64=0
next=()=>{count+=1 return 14}
combine=(a:int64=next() b:int64=a c:int64=b)=>a+b+c
main=()=>{let value=combine() return if count =? 1 value else 1}''',
    'default-reference-generic': '''combine=(a b=a)=>a+b
main=()=>combine(21)''',
    'default-reference-named': '''let count:int64=0
next=()=>{count+=1 return count}
combine=(a:int64 b:int64 c:int64=a)=>a*10+b+c
main=()=>if combine(b=next() a=next()) =? 23 and count =? 2 42 else 1''',
    'default-reference-nested': '''identity=(value:int64)=>value
combine=(a:int64 b:int64=identity(a))=>a+b
main=()=>{let x:int64=21 return combine(x)}''',
    'default-reference-managed': '''combine=(a:array<int64> b:array<int64>=a)=>{
b[0]=99 return a[0]+a[1]}
main=()=>combine([20 22])''',
    'default-reference-field': '''Item:type=[value:int64]
combine=(a:Item b:int64=a.value)=>a.value+b
main=()=>combine(Item[21])''',
    'default-reference-return-managed': '''copy=(a:array<int64> b:array<int64>=a)=>b
main=()=>{let values=copy([20 22]) return values[0]+values[1]}''',
    'default-reference-global': '''combine=(a:int64 b:int64=a)=>a+b
let answer=combine(21)
main=()=>answer''',
    'default-reference-float': '''combine=(a:float64 b:float64=a)=>a+b
main=()=>if combine(21) =? 42.0 42 else 1''',
    'default-reference-closure': '''Getter:type=():>int64
combine=(a:int64 getter:Getter=()=>a)=>a+getter()
main=()=>combine(21)''',
    'default-reference-closure-return': '''Getter:type=():>int64
create=(a:int64 getter:Getter=()=>a):>Getter=>getter
main=()=>{let getter=create(42) return getter()}''',
    'default-reference-shadow': '''combine=(a:int64 b:int64={let a:int64=2 a} c:int64=a)=>a+c+b
main=()=>combine(20)''',
    'named-interleaved': '''add=(x:int64 y:int64=2 z:int64)=>x+y+z
main=()=>add(y=2 20 20)''',
    'named-order': '''let sequence:int64=0
next=()=>{sequence+=1 return sequence}
combine=(a:int64 b:int64)=>a*10+b
main=()=>if combine(b=next() a=next()) =? 21 and sequence =? 2 42 else 1''',
    'named-default-order': '''let sequence:int64=0
next=()=>{sequence+=1 return sequence}
combine=(a:int64=next() b:int64=next())=>a*10+b
main=()=>if combine(b=next()) =? 21 and sequence =? 2 42 else 1''',
    'named-constructor-order': '''Pair:type=[a:int64 b:int64]
let sequence:int64=0
next=()=>{sequence+=1 return sequence}
main=()=>{let p=Pair[b=next() a=next()] return if p.a*10+p.b =? 21 42 else 1}''',
    'named-managed-order': '''let values:array<int64>=[40]
replace=()=>{values=[99] return 2}
combine=(n:int64 xs:array<int64>)=>xs[0]+n
main=()=>combine(xs=values n=replace())''',
    'named-place': '''add=(x:int64 @out:int64):>void=>{out+=x}
main=()=>{let answer:int64=40 add(out=@answer 2) return answer}''',
    'named-generic-order': '''let sequence:int64=0
next=()=>{sequence+=1 return sequence}
combine=(a b)=>a*10+b
main=()=>if combine(b=next() a=next()) =? 21 and sequence =? 2 42 else 1''',
    'named-record-snapshot': '''Item:type=[values:array<int64>]
let item=Item[[40]]
replace=()=>{item=Item[[99]] return 2}
combine=(n:int64 old:Item)=>old.values[0]+n
main=()=>combine(old=item n=replace())''',
    'argument-float-snapshot': '''add=(x:float64 y:float64)=>x+y
main=()=>{let x:float64=40.0 return if add(x {x=99.0 2.0}) =? 42.0 42 else 1}''',
    'argument-snapshot': '''add=(x:int64 y:int64)=>x+y
main=()=>{let x:int64=40 return add(x {x=99 2})}''',
    'default-field': 'Value:type=[x:int64=42]\nmain=()=>Value[].x',
    'closure': 'main=()=>{let x:int64=40 let f=(n:int64)=>x+n return f(2)}',
    'closure-state': '''main=()=>{let x:int64=40 let f=()=>{x+=1 return x}
f(); return f()}''',
    'higher-order': 'apply=(f x)=>f(x)\nmain=()=>apply((x:int64)=>x+2 40)',
    'forward-record': 'main=()=>Value[42].x\nValue:type=[x:int64]',
    'length-field': 'Span:type=[length:int64]\nmain=()=>{let s=Span[40] s.length+=2 return s.length}',
    'growing-loop': '''main=()=>{let xs:array<int64>=[10] let sum:int64=0
loop i in 0.. and i <? xs.length {sum+=xs[i] if i =? 0 xs.push(32)} return sum}''',
    'shrinking-loop-call': '''trim=(@xs:array<int64>):>void=>{xs.pop();}
main=()=>{let xs:array<int64>=[20 22 99] let sum:int64=0
loop i in 0.. and i <? xs.length {sum+=xs[i] trim(@xs)} return sum}''',
    'shrinking-global-loop': '''let xs:array<int64>=[20 22 99]
trim=():>void=>{xs.pop();}
main=()=>{let sum:int64=0 loop i in 0.. and i <? xs.length {sum+=xs[i] trim()} return sum}''',
    'shrinking-loop-condition': '''let xs:array<int64>=[10 20 12 99]
let index:int64=0
keep=()=>{if xs.length >? 2 {xs.pop();} return index <? xs.length}
main=()=>{let sum:int64=0 loop keep() {sum+=xs[index]+xs.length index+=1} return sum+7}''',
    'growing-loop-condition': '''let xs:array<int64>=[20]
let index:int64=0
keep=()=>{if index =? 1 {xs.push(22)} return index <? xs.length}
main=()=>{let sum:int64=0 loop keep() {sum+=xs[index] index+=1} return sum}''',
    'captured-array': '''main=()=>{let xs:array<int64>=[40] let original=xs
let bump=($capture @xs)=>{xs[0]+=1} bump() bump() return if original[0]=?40 xs[0] else 1}''',
    'type-alias': 'Count:type=int64\nmain=()=>{let x:Count=42 return x}',
    'union': '''Choice:type=int64|string
value=(x:Choice):>int64=>if x is? int64 x else 0
main=()=>value(42)+value("ignored")''',
    'union-inverse': '''value=(x:int64|string):>int64=>if x isnt? int64 0 else x
main=()=>value(42)+value("ignored")''',
    'optional-return': '''choose=(yes:bool):>int64?=>if yes 42 else none
main=()=>{let a=choose(true) let b=choose(false)
return if a is? int64 and b is? none a else 1}''',
    'generic-optional-suffix': """choose=(yes:bool):>array<uint16>?=>if yes [20 22] else none
sum=(values:array<uint16>?):>int64=>if values is? none 0 else values[0]+values[1]
main=()=>{let empty:array<uint16>?=none let present:array<uint16>?=[20 22]
return if sum(empty)=?0 and sum(choose(false))=?0 and sum(choose(true))=?42
and 5>?3 and not (3>?5) sum(present) else 1}""",
    'generic-optional-nested-suffix': """read=(values:array<array<uint16>?>?):>int64=>{
if values is? none return 0
let first=values[0] let second=values[1]
return if first is? none and second isnt? none second[0]+second[1] else 1}
main=()=>{let absent:array<array<uint16>?>?=none
let present:array<array<uint16>?>?=[none [20 22]]
return if read(absent)=?0 read(present) else 1}""",
    'optional-union': '''value=(x:(int64|string)?):>int64=>if x is? int64 x else if x is? string 2 else 0
main=()=>value(40)+value("two")+value(none)''',
    'optional-dictionary': '''main=()=>{let d=["a"->42] let hit=d.get("a") let miss=d.get("b")
return if hit isnt? none and miss is? none hit else 1}''',
    'optional-managed-copy': '''Item:type=[values:array<int64>]
main=()=>{let a:Item?=Item[[20 22]] let b=a
if b is? Item b.values[0]=99
return if a is? Item a.values[0]+a.values[1] else 1}''',
    'optional-array': '''main=()=>{let xs:array<int64?>=[20 none 22] let sum:int64=0
loop x in xs {if x is? int64 sum+=x} return sum}''',
    'match-union-subset-binding': '''TextOrCount:type=int64|string
read=(v:TextOrCount):>int64=>if v is? int64 v else v.length
pick=(v:TextOrCount|bool):>int64=>match v {part:TextOrCount=>read(part) <bool>=>2}
main=()=>pick(37)+pick("abc")+pick(true)''',
    'match-union-subset-narrow': '''read=(v:int64|string):>int64=>if v is? int64 v else v.length
pick=(v:int64|string|bool):>int64=>match v {<int64|string>=>read(v) _=>if v 2 else 0}
main=()=>pick(37)+pick("abc")+pick(true)+pick(false)''',
    'match-union-subset-path': '''Envelope:type=[value:int64|string|bool]
read=(v:int64|string):>int64=>if v is? int64 v else v.length
pick=(box:Envelope):>int64=>match box.value {<int64|string>=>read(box.value) _=>if box.value 2 else 0}
main=()=>pick(Envelope[37])+pick(Envelope["abc"])+pick(Envelope[true])''',
    'match-union-subset-copy': '''Numbers:type=[values:array<int64>]
main=()=>{let original:Numbers|string|bool=Numbers[[20 22]]
let result=match original {part:Numbers|string=>{
if part is? string return 1
part.values[0]=99
part.values[1]} <bool>=>0}
return if original is? Numbers original.values[0]+result else 1}''',
    'match-union-subset-overlap': '''pick=(v:int64|string|bool):>int64=>match v {
<int64|string>=>20 <bool|string>=>2}
main=()=>pick(0)+pick("first arm")+pick(true)''',
    'match-union-subset-generic': '''read=(v:int64|string):>int64=>if v is? int64 v else v.length
pick=<T>(v:T|bool):>int64=>match v {part:T=>read(part) <bool>=>2}
main=()=>pick<int64|string>(37)+pick<int64|string>("abc")+pick<int64|string>(true)''',
    'match-union-literals': '''pick=(v:int64|string):>int64=>match v {
<0>=>1 s:"yes"=>s.length+v.length <"no">=>0 n:42=>n _=>2}
main=()=>pick(0)+pick("yes")+pick("no")+pick(42)-pick(8)-pick("other")-3''',
    'match-union-bool-exhaustive': '''pick=(v:bool|string):>int64=>match v {
<true>=>20 <false>=>19 _=>v.length}
main=()=>pick(true)+pick(false)+pick("abc")''',
    'match-union-partial-fallback': '''pick=(v:int64|string):>int64=>match v {
<0>=>0 <"yes">=>1 _=>if v is? int64 v else v.length}
main=()=>pick(0)+pick("yes")+pick(38)+pick("abc")''',
    'match-union-literal-path': '''Envelope:type=[value:int64|string]
pick=(box:Envelope):>int64=>match box.value {
<"yes">=>box.value.length <0>=>box.value n:int64=>n _=>box.value.length}
main=()=>pick(Envelope["yes"])+pick(Envelope[0])+pick(Envelope[36])+pick(Envelope["abc"])''',
    'match-union-literal-snapshot': '''let calls:int64=0
let source:int64|string="answer"
next=():>int64|string=>{calls+=1 return source}
main=()=>{let result=match next() {s:"answer"=>{source=99 s.length} _=>0}
return if calls=?1 and source is? int64 result*7 else 1}''',
    'match-union-literal-widths': '''pick=(v:uint8|string):>int64=>match v {<255>=>20 <0>=>1 _=>0}
wide=(v:uint64|string):>int64=>match v {<18446744073709551615>=>21 _=>0}
main=()=>pick(255)+pick(0)+pick("x")+wide(18446744073709551615)+wide("x")''',
    'match-union-literal-member': '''pick=(v:int64|uint8|string):>int64=>match v {
<42>=>40 <uint8>=>2 _=>0}
main=()=>{let small:uint8=42 return pick(42)+pick(small)+pick("42")}''',
    'match-union': '''Count:type=int64
classify=(v:bool|Count|string):>int64=>match v {
<bool>=>10 n:Count=>n s:string=>s.length}
main=()=>classify(true)+classify(29)+classify("abc")''',
    'match-integers': '''pick=(v:int64)=>match v {<-1>=>1 answer:42=>answer <3>=>3 rest=>rest+1}
main=()=>pick(-1)+pick(42)-pick(3)+pick(1)''',
    'match-strings': '''pick=(s:string)=>match s {<"yes">=>40 <"no">=>0 _=>2}
main=()=>pick("yes")+pick("maybe")+pick("no")''',
    'match-bools': '''pick=(b:bool)=>match b {<true>=>40 <false>=>2}
main=()=>pick(true)+pick(false)''',
    'match-optional': '''pick=(v:int64?)=>match v {<none>=>2 n:int64=>n}
main=()=>pick(40)+pick(none)''',
    'match-else-chain': '''pick=(v:int64|string flag:bool)=>match v {n:int64=>n} else if flag 2 else 0
main=()=>pick(40 false)+pick("text" true)+pick("text" false)''',
    'match-generic': '''identity=(v)=>match v {x=>x}
main=()=>identity(39)+identity("abc").length''',
    'match-union-narrow': '''pick=(v:int64|string)=>match v {<int64>=>v _=>v.length}
main=()=>pick(39)+pick("abc")''',
    'match-single-arm': 'main=()=>match 42 n:int64=>n',
    'match-evaluate-once': '''let calls:int64=0
next=()=>{calls+=1 return 40}
main=()=>{let value=match next() {<0>=>0 n:int64=>n} return value+calls*2}''',
    'match-copy': '''Item:type=[values:array<int64>]
main=()=>{let a:Item|string=Item[[20 22]]
let result=match a {b:Item=>{b.values[0]=99 b.values[1]} <string>=>0}
return if a is? Item a.values[0]+result else 1}''',
    'match-optional-copy': '''Numbers:type=array<int64>
main=()=>{let a:Numbers?=[20 22]
let result=match a {b:Numbers=>{b[0]=99 b[1]} <none>=>0}
return if a is? Numbers a[0]+result else 1}''',
    'match-return': '''pick=(v:int64|string):>int64=>{match v {n:int64=>return n s:string=>return s.length}}
main=()=>pick(39)+pick("abc")''',
    'match-statement': '''main=()=>{let result:int64=0 match true {<true>=>{result=42} <false>=>{result=1}} return result}''',
    'function-type': '''Fn:type=(x:int64):>int64
apply=(f:Fn x:int64):>int64=>f(x)
main=()=>apply((x:int64)=>x+2 40)''',
    'mutable-function-type': '''Fn:type=(@x:int64):>void
apply=(f:Fn @x:int64):>void=>{f(@x)}
main=()=>{let x:int64=40 apply((@a:int64):>void=>{a+=2} @x) return x}''',
    'dictionary': '''main=()=>{let a:dict<string int64>=["a"->20 "b"->22]
let b=a b["a"]=0 return a["a"]+a["b"]}''',
    'empty-dictionary': '''Values:type=dict<string int64>
main=()=>{let a:Values=[] a["answer"]=42 return a["answer"]}''',
    'dictionary-iteration': '''main=()=>{let a:dict<int64 int64>=[1->19 2->20]
let sum:int64=0 loop [k v] in a {sum+=k+v} return sum}''',
    'dictionary-counted-keys': '''main=()=>{let values=["a"->10 "b"->20]
let count:int64=0
loop i in 0.. and key in values {
if i =? 0 and key not=? "a" return 1
if i =? 1 and key not=? "b" return 2
count+=1
}
return if count =? 2 42 else 3}''',
    'dictionary-counted-sparse': '''main=()=>{let values=[100->1 200->2]
let count:int64=0
loop i in 0.. and key in values {if key not=? (i+1)*100 return 1 count+=1}
return if count =? 2 42 else 2}''',
    'dictionary-zip-keys': '''main=()=>{let values=["a"->1 "b"->2]
let total:int64=0
loop key in values and score in [20 22] {if key =? "a" or key =? "b" total+=score}
return total}''',
    'dictionary-zip-pairs': '''main=()=>{let values=["a"->[10 11] "b"->[10 11]]
let total:int64=0
loop [key [x y]] in values and weight in [1 1] {total+=(x+y)*weight}
return total}''',
    'dictionary-zip-wide-record': '''main=()=>{let values=[uint64.max->[x=20 y=22]]
let total:int64=0
loop [key [x y]] in values and marker in [1] {
if key not=? uint64.max return 1 total+=(x+y)*marker
}
return total}''',
    'dictionary-zip-removed': '''main=()=>{let values=["gone"->99 "a"->20 "b"->22]
values.remove("gone") let total:int64=0
loop [key value] in values and expected in [20 22] {
if key =? "gone" or value not=? expected return 1 total+=value
}
let count:int64=0
loop i in 0.. and key in values {if key =? "gone" or i >? 1 return 2 count+=1}
return if count =? 2 total else 3}''',
    'dictionary-zip-copy': '''main=()=>{let values=["a"->[20] "b"->[22]]
let total:int64=0
loop [key value] in values and index in [0 1] {
total+=value[0] value[0]=0 values["b"]=[99] values["c"]=[100]
}
return total}''',
    'dictionary-zip-source-order': '''let trace:int64=0
entries=()=>{trace=trace*10+1 return ["a"->20 "b"->22]}
weights=()=>{trace=trace*10+2 return [1 1]}
main=()=>{let total:int64=0
loop [key value] in entries() and weight in weights() {total+=value*weight}
return if trace =? 12 total else 1}''',
    'dictionary-zip-or': '''main=()=>{let values=["a"->99]
let total:int64=0 let keys:int64=0
loop key in values or value in [20 22] {
if key isnt? none {if key not=? "a" return 1 keys+=1}
total+=value??0
}
return if keys =? 1 total else 2}''',
    'dictionary-zip-empty': '''main=()=>{let values:dict<string int64>=[]
let total:int64=0
loop key in values and value in [99] {return 1} else {total=20}
loop key in values or value in [22] {if key isnt? none return 2 total+=value??0}
return total}''',
    'dictionary-iterator-sparse-snapshot': '''main=()=>{
let values=[0->[0] 1->[99] 2->[20] 3->[22] 4->[99]]
values.remove(1) values.remove(4)
let total:int64=0 let seen:array<int64>=[]
loop [key value] in values {
seen.push(key) total+=value[0]
values.remove(0) values.remove(2) values[3]=[999] values[5]=[999]
let copy=value copy[0]=100
}
return if seen =? [0 2 3] and total =? 42 and values[3] =? [999] 42 else 1}''',
    'dictionary-iterator-counted-order': '''main=()=>{
let values=[0->1 1->1 2->1 3->1 4->1 5->1]
values.remove(0) values.remove(2) values.remove(5) values[6]=1
let expected=[1 3 4 6] let count:int64=0
loop i in 0.. and key in values {
if key not=? expected[i] return 1
count+=1 if i =? 1 continue
values[7]=1 values.remove(3)
}
return if count =? 4 42 else 2}''',
    'dictionary-iterator-allocation-budget': '''main=()=>{
let values=[0->[0] 1->[99] 2->[20] 3->[22] 4->[99]]
values.remove(1) values.remove(4)
let before=alloc_count() let total:int64=0
loop [key value] in values {if alloc_count() >? before+2 return 1 total+=value[0]}
loop i in 0.. and key in values {if alloc_count() >? before+2 return 2}
loop [key value] in values and i in [0..3) {if alloc_count() >? before+2 return 3}
return total}''',
    'dictionary-iterator-zip-exhaustion': '''main=()=>{
let values=[0->0 1->99 2->20 3->22 4->99]
values.remove(1) values.remove(4)
let count:int64=0 let total:int64=0
loop [key value] in values and i in [0..10) {
count+=1 if key =? 0 continue total+=value
values.clear()
}
if count not=? 3 or total not=? 42 return 1
values=[1->99 2->20 3->99] values.remove(1) values.remove(3)
count=0 total=0
loop key in values or value in [20 22 0] {
if key isnt? none {if key not=? 2 return 2 count+=1}
total+=value??0
}
return if count =? 1 total else 3}''',
    'dictionary-iterator-exit-cleanup': '''work=()=>{
let values=["first"->[20] "gone"->[99] "last"->[22]] values.remove("gone")
let result:int64=0
$outer loop [key value] in values {
loop i in 0.. and inner in values {
if i =? 0 continue
result+=value[0] break $outer
}
}
loop [key value] in values and i in [0..2) {
if i =? 0 continue
return result+value[0]
}
return 1
}
main=()=>{if work() not=? 42 return 1 let before=alloc_count()
loop i in [0..30) {if work() not=? 42 return 2}
return if alloc_count() =? before 42 else 3}''',
    'dictionary-length': 'main=()=>{let a=["a"->1 "b"->2] return a.length+40}',
    'dictionary-insert-absent': '''main=()=>{let values:dict<string int64>=[]
if not values.insert_if_absent("first" 20) return 1
if values.insert_if_absent("first" 99) return 2
if not values.insert_if_absent("second" 22) return 3
if values.keys() not=? ["first" "second"] return 4
return values["first"]+values["second"]}''',
    'dictionary-insert-copy': '''main=()=>{let values=["one"->[20]] let snapshot=values
let incoming=[22]
if not values.insert_if_absent("two" incoming) return 1
incoming[0]=99
values["one"].push(7)
if values.insert_if_absent("one" [99]) return 2
if snapshot.length not=? 1 or snapshot["one"] not=? [20] return 3
if values["one"] not=? [20 7] return 4
return snapshot["one"][0]+values["two"][0]}''',
    'dictionary-insert-arguments': '''let calls:int64=0
key=()=>{calls=calls*10+1 return "key"}
value=()=>{calls=calls*10+2 return 42}
main=()=>{let values:dict<string int64>=[]
if not values.insert_if_absent(key() value()) or calls not=? 12 return 1
calls=0
if values.insert_if_absent(key() value()) or calls not=? 12 return 2
return values["key"]}''',
    'dictionary-projection-sparse': '''main=()=>{
let values=[10->1 20->2 30->3 40->4 50->5]
values.remove(20) values.remove(40) values[60]=6
if values.keys() not=? [10 30 50 60] or values.values() not=? [1 3 5 6] return 1
values[20]=22
return if values.keys() =? [10 30 50 60 20] and values.values() =? [1 3 5 6 22] 42 else 2}''',
    'dictionary-projection-managed-snapshots': '''main=()=>{
let values=[[1]->[10] [2]->[20] [3]->[30] [4]->[40]]
values.remove([2])
let saved=values let keys=values.keys() let items=values.values()
keys[0][0]=99 items[0][0]=999
if values[[1]] not=? [10] or saved[[1]] not=? [10] return 1
values[[3]][0]=300 values.remove([4]) values[[5]]=[50]
return if keys =? [[99] [3] [4]] and items =? [[999] [30] [40]]
and saved.keys() =? [[1] [3] [4]] and saved.values() =? [[10] [30] [40]] 42 else 2}''',
    'dictionary-projection-zero-values': '''main=()=>{
let values:dict<int64 int64?>=[1->none 2->22 3->0 4->none]
values.remove(2)
if values.keys() not=? [1 3 4] or values.values() not=? [none 0 none] return 1
values.remove(1) values.remove(3) values.remove(4)
return if values.keys() =? [] and values.values() =? [] 42 else 2}''',
    'dictionary-projection-release': '''work=():>void=>{
let values=["first"->[20] "gone"->[99] "last"->[22]] values.remove("gone")
let keys=values.keys() let items=values.values()
if keys not=? ["first" "last"] or items not=? [[20] [22]] panic("projection")
}
main=()=>{work() let before=alloc_count() loop i in [0..30) work()
return if alloc_count() =? before 42 else 1}''',
    'dictionary-key-word-boundaries': '''main=()=>{
let signed=[int64.min int64.max -1 0 4294967295 4294967296 -4294967296]
let values:dict<int64 array<int64>>=[]
loop i in [0..signed.length) values[signed[i]]=[i]
let saved=values
values.reserve(100)
loop i in [0..signed.length) {
if values.get(signed[i]) is? none or values[signed[i]] not=?[i] return 1
values[signed[i]].push(42)
if saved[signed[i]] not=?[i] return 2
}
if values.has(1) or values.has(-4294967295) return 3
loop i in [0..4) {if not values.remove(signed[i]) return 4}
loop i in [0..4) values[signed[i]]=[42]
if values.keys() not=?[4294967295 4294967296 -4294967296 int64.min int64.max -1 0] return 5
let unsigned:array<uint64>=[0 uint64.max uint64.max-1 4294967295 4294967296]
let wide:dict<uint64 int64>=[]
loop i in [0..unsigned.length) wide[unsigned[i]]=i
let prior=wide
wide.remove(uint64.max) wide.reserve(100) wide[uint64.max]=42
loop i in [0..unsigned.length) {
if prior[unsigned[i]] not=?i return 6
if wide[unsigned[i]] not=? (if i=?1 42 else i) return 7
}
return if not wide.has(1 as uint64) 42 else 8}''',
    'dictionary-full-hash-collisions': '''Key:type=[value:int64 label:string]
hash=(key:Key):>uint64=>0
__eq__=(a:Key b:Key):>bool=>a.value=?b.value
main=()=>{
let values:dict<Key array<int64>>=[]
loop i in [0..80) values[Key[i "first"]]=[i]
let saved=values
loop i in [0..61) {if not values.remove(Key[i "remove"]) return 1}
if values.has(Key[100 "missing"]) return 2
values.reserve(300)
loop i in [0..61) {
if not values.insert_if_absent(Key[i "again"] [i+100]) return 3
}
loop i in [0..80) {
if values.insert_if_absent(Key[i "duplicate"] [999]) return 4
if saved[Key[i "snapshot"]] not=?[i] return 5
if values[Key[i "lookup"]] not=?[if i<?61 i+100 else i] return 6
}
let keys=values.keys()
if keys.length not=?80 or keys[0].value not=?61 or keys[19].value not=?0 return 7
values[Key[0 "mutate"]].push(42)
return if saved[Key[0 "original"]]=?[0] 42 else 8}''',
    'dictionary-insert-growth': '''main=()=>{let values:dict<int64 int64>=[]
loop i in [0..300) {if not values.insert_if_absent(i i+1) return 1}
let snapshot=values
loop i in [0,2..300) {if not values.remove(i) return 2}
loop i in [0..300) {
let added=values.insert_if_absent(i i+42)
if added not=? (i%2 =? 0) return 3
if values[i] not=? (if added i+42 else i+1) return 4
if snapshot[i] not=? i+1 return 5
}
let keys=values.keys()
if keys[0] not=? 1 or keys[149] not=? 299 or keys[150] not=? 0 or keys[299] not=? 298 return 6
return if values.length=?300 42 else 7}''',
    'records': '''Vector:type=[x:int64 y:int64]
main=():>int64=>{let a=Vector[20 22] let b=a b.x=0 return a.x+a.y}''',
    'record-context': '''Vector:type=[x:int64 y:int64=2]
main=()=>{let value:Vector=[x=40] return value.x+value.y}''',
    'record-return': '''Vector:type=[x:int64 y:int64]
make=():>Vector=>[y=22 x=20]
main=()=>{let v=make() return v.x+v.y}''',
    'record-argument': '''Vector:type=[x:int64 y:int64]
sum=(v:Vector)=>v.x+v.y
main=()=>sum([y=22 x=20])''',
    'record-nested': '''Inner:type=[values:array<int64>]
Outer:type=[inner:Inner]
main=()=>{let a:Outer=[inner=[values=[20 22]]] let b=a b.inner.values[0]=99
return a.inner.values[0]+a.inner.values[1]}''',
    'record-anonymous': '''main=()=>{let a=[x=20 y=22] let b=a b.x=99 return a.x+a.y}''',
    'record-anonymous-nested': '''main=()=>{let a=[inner=[values=[20 22]]] let b=a
b.inner.values[0]=99 return a.inner.values[0]+a.inner.values[1]}''',
    'record-anonymous-shape': '''main=()=>{let a=[x=1 y=2] let b=[y=22 x=20]
a=b return a.x+a.y}''',
    'record-anonymous-array': '''main=()=>{let values=[[x=20 y=1] [y=2 x=22]]
return values[0].x+values[1].x}''',
    'record-inline-parameter': '''sum=(point:[x:int64 y:int64])=>point.x+point.y
main=()=>{let point=[y=22 x=20] return sum(point)}''',
    'record-inline-return': '''make=():>[y:int64 x:int64]=>[x=20 y=22]
main=()=>{let point:[x:int64 y:int64]=make() return point.x+point.y}''',
    'record-inline-global': '''let point:[x:int64 y:int64]=[y=22 x=20]
main=()=>point.x+point.y''',
    'record-inline-nested': '''main=()=>{let first:[inner:[values:array<int64>]]=[inner=[values=[20 22]]]
let second=first second.inner.values[0]=99 return first.inner.values[0]+first.inner.values[1]}''',
    'record-inline-array': '''main=()=>{let points:array<[x:int16 y:int16]>=[[y=2 x=20] [x=22 y=3]]
return (points[0].x+points[1].x) as int64}''',
    'record-inline-map': '''main=()=>{let points:dict<string [x:int64]>=["answer"->[x=42]]
return points["answer"].x}''',
    'record-inline-optional': '''pick=(point:[x:int64]?)=>if point is? none 2 else point.x
main=()=>pick([x=40])+pick(none)''',
    'record-inline-function-type': '''Apply:type=(point:[x:int64]):>int64
main=()=>{let f:Apply=(point:[x:int64])=>point.x return f([x=42])}''',
    'record-inline-place': '''bump=(@point:[x:int64]):>void=>{point.x+=2}
main=()=>{let point=[x=40] let original=point bump(@point) return if original.x =? 40 point.x else 1}''',
    'record-inline-named-field': '''Outer:type=[point:[x:int64 y:int64]]
main=()=>{let outer:Outer=[point=[y=22 x=20]] return outer.point.x+outer.point.y}''',
    'record-inline-empty': '''answer=(value:[])=>42
main=()=>answer([])''',
    'record-inline-match': '''pick=(value:[answer:int64]?)=>match value {item:[answer:int64]=>item.answer <none>=>0}
main=()=>pick([answer=42])''',
    'record-inline-overload': '''read=(value:[answer:int64])=>value.answer
read=(value:[answer:string])=>value.answer.length
main=()=>read([answer=39])+read([answer="abc"])''',
    'record-inline-default': '''read=(value:[answer:int64]=[answer=42])=>value.answer
main=()=>read()''',
    'record-generic': '''sum=(v)=>v.x+v.y
main=()=>sum([y=22 x=20])''',
    'record-order': '''let sequence:int64=0
next=()=>{sequence+=1 return sequence}
main=()=>{let v=[y=next() x=next()] return if v.y*10+v.x =? 12 42 else 1}''',
    'record-overload': '''Integer:type=[value:int64]
Text:type=[value:string]
read=(v:Integer)=>v.value
read=(v:Text)=>v.value.length
main=()=>read([value=39])+read([value="abc"])''',
    'record-context-order': '''Pair:type=[a:int64 b:int64]
let sequence:int64=0
next=()=>{sequence+=1 return sequence}
main=()=>{let p:Pair=[b=next() a=next()] return if p.b*10+p.a =? 12 42 else 1}''',
    'record-optional': '''Value:type=[answer:int64]
get=(v:Value?)=>if v is? Value v.answer else 0
main=()=>get([answer=42])''',
    'record-empty-context': '''Value:type=[answer:int64=42]
main=()=>{let value:Value=[] return value.answer}''',
    'record-empty-argument': '''Value:type=[answer:int64=42]
get=(value:Value?)=>if value is? Value value.answer else 0
main=()=>get([])''',
    'unpack-param-default-shadow': '''apply=(@x:int64 callback=([[x]]:array<array<int64>>)=>x)=>callback([[42]])
main=()=>{let value=1 return apply(@value)}''',
    'unpack-param-default-once': '''let counter=0
next=()=>{counter+=1 return [20 22]}
sum=([a b]=next())=>a+b
main=()=>{let answer=sum() if counter not=?1 return 1 return answer}''',
    'unpack-nested-default-shadow': '''apply=(@x:int64 value:int64={let [[x]]=[[42]] x})=>value
main=()=>{let value=1 return apply(@value)}''',
    'unpack-loop-default-shadow': '''apply=(@x:int64 values:array<int64>=[loop [[x] [y]] in [[[20] [22]]] x+y])=>values[0]
main=()=>{let value=1 return apply(@value)}''',
    'unpack-param-array': 'sum=([a b])=>a+b\nmain=()=>sum([20 22])',
    'unpack-param-typed': 'sum=([a b]:array<int64>)=>a+b\nmain=()=>sum([20 22])',
    'unpack-param-record': 'sum=([y x]:[x:int64 y:int64])=>x+y\nmain=()=>sum([x=20 y=22])',
    'unpack-param-nested': 'sum=([[a b] [_ c]])=>a+b+c\nmain=()=>sum([[10 12] [99 20]])',
    'unpack-param-fixed': 'sum=([a b]:array<int64 length=2>)=>a+b\nmain=()=>sum([20 22])',
    'unpack-param-generic': 'sum=<T>([a b]:array<T>):>T=>a+b\nmain=()=>sum<int64>([20 22])',
    'unpack-param-default': 'sum=([a b]=[20 22])=>a+b\nmain=()=>sum()',
    'unpack-param-closure': '''make=(bias:int64)=>(([a b]:array<int64>)=>a+b+bias)
main=()=>{let add=make(2) return add([20 20])}''',
    'unpack-param-callback': '''apply=(f:((xs:array<int64>):>int64))=>f([20 22])
main=()=>apply(([a b])=>a+b)''',
    'unpack-param-value': '''change=([a b]:array<array<int64>>)=>{a[0]+=2 b.push(99) return a[0]+b[0]}
main=()=>{let values=[[20] [20]] let answer=change(values)
if values not=?[[20] [20]] return 1
return answer}''',
    'unpack-param-order': '''let counter=0
pair=()=>{counter+=1 return [counter 20]}
last=()=>{counter+=10 return counter}
sum=([a b] tail:int64)=>if a=?1 and b=?20 and tail=?11 and counter=?11 42 else 1
main=()=>sum(pair() last())''',
    'unpack-param-captured-copy': '''make=([a]:array<array<int64>>)=>()=>{a[0]+=1 return a[0]}
main=()=>{let values=[[40]] let next=make(values)
if next() not=?41 or values[0][0] not=?40 return 1
return next()}''',
    'unpack-param-snapshot': '''let values=[20 22]
change=()=>{values[0]=99 return 0}
sum=([a b] ignored:int64)=>a+b
main=()=>sum(values change())''',
    'unpack-param-named': 'sum=([a b] extra:int64=2)=>a+b+extra\nmain=()=>sum(extra=2 [20 20])',
    'unpack-param-dictionary': '''sum=([[key value] [_ other]])=>value+other+key.length
main=()=>sum(["hi"->20 "there"->20])''',
    'unpack-array': 'main=()=>{let [x y]=[20 22] return x+y}',
    'unpack-leaf-types': '''main=()=>{let [x:int64 y:float64]=[20 22]
return if y is?float64 and x=?20 and y=?22.0 42 else 1}''',
    'unpack-leaf-types-once': '''let calls=0
pair=()=>{calls+=1 return [20 22]}
main=()=>{const [x:int64 y:float64]=pair()
return if y is?float64 and x=?20 and y=?22.0 and calls=?1 42 else 1}''',
    'unpack-leaf-types-global': '''const [x:int64 y:float64]=[20 22]
main=()=>if y is?float64 and x=?20 and y=?22.0 42 else 1''',
    'unpack-leaf-types-record': '''main=()=>{
let [x:float64 y:int64]=[y=22 x=20 z=99]
return if x is?float64 and x=?20.0 and y=?22 42 else 1}''',
    'unpack-leaf-types-nested': '''main=()=>{let [[x:float64] [y:int64]]=[[20] [22]]
return if x is?float64 and x=?20.0 and y=?22 42 else 1}''',
    'unpack-leaf-types-context': '''main=()=>{
let [x:int64 y:float64]:array<uint8>=[20 22]
return if y is?float64 and x=?20 and y=?22.0 42 else 1}''',
    'unpack-leaf-types-fixed': '''main=()=>{
let [x:int64 y:float64]:array<uint8 length=2>=[20 22]
return if y is?float64 and x=?20 and y=?22.0 42 else 1}''',
    'unpack-leaf-types-param': '''combine=([x:int64 y:float64])=>if y is?float64 and x=?20 and y=?22.0 42 else 1
main=()=>combine([20 22])''',
    'unpack-leaf-types-generic': '''combine=<T>([x:T y:float64]:array<T>)=>if y is?float64 and x=?20 and y=?22.0 42 else 1
main=()=>combine<uint8>([20 22])''',
    'unpack-leaf-types-closure': '''make=([x:int64 y:float64])=>()=>if y is?float64 and x=?20 and y=?22.0 42 else 1
main=()=>{let f=make([20 22]) return f()}''',
    'unpack-leaf-types-loop': '''main=()=>{let result=0
loop [x:int64 y:float64] in [[20 22]] {if y is?float64 and x=?20 and y=?22.0 result=42}
return result}''',
    'unpack-leaf-types-loop-single': '''main=()=>{let result=0
loop [x:float64] in [[42]] {if x is?float64 and x=?42.0 result=42}
return result}''',
    'unpack-leaf-types-combined': '''main=()=>{let result=0
loop i in [0..1) and [x:int64 y:float64] in [[20 22]] {if y is?float64 and x=?20 and y=?22.0 result=42+i}
return result}''',
    'unpack-leaf-types-managed': '''main=()=>{
let source=[[20] [22]] let [x:array<int64> y:array<int64>]=source
x[0]=99 return if source=?[[20] [22]] and y=?[22] 42 else 1}''',
    'unpack-leaf-types-discard': '''main=()=>{let [_:float64 x:int64]=[1 42] return x}''',
    'unpack-leaf-types-loop-record': '''main=()=>{let result=0
loop [x:int64 y:float64] in [[x=20 y=22]] {if y is?float64 and x=?20 and y=?22.0 result=42}
return result}''',
    'unpack-leaf-types-loop-dictionary': '''main=()=>{let result=0
loop [key:int64 value:float64] in [20->22] {if value is?float64 and key=?20 and value=?22.0 result=42}
return result}''',
    'unpack-leaf-types-loop-sequence': '''Rows:type=[values:array<[x:int64 y:int64]>]
len=(rows:Rows)=>rows.values.length
__index__=(rows:Rows i:int64)=>rows.values[i]
main=()=>{let result=0
loop [x:int64 y:float64] in Rows[[[x=20 y=22]]] {if y is?float64 and x=?20 and y=?22.0 result=42}
return result}''',
    'unpack-typed-narrow': '''byte=(x:uint8)=>x as int64
main=()=>{let [a b]:array<uint8>=[20 22] return byte(a)+byte(b)}''',
    'unpack-typed-nested-fixed': '''main=()=>{
let [[a b] [c d]]:array<array<int64 length=2> length=2>=[[10 12] [9 11]]
return a+b+c+d}''',
    'unpack-typed-record': '''main=()=>{
let [y x]:[x:int64 y:int64 z:int64]=[x=20 y=22 z=99]
return x+y}''',
    'unpack-typed-generic': '''combine_parts=<T>(values:array<T>)=>{let [a b]:array<T>=values return a+b}
main=()=>if combine_parts(["he" "llo"])=?"hello" combine_parts([20 22]) else 1''',
    'unpack-const-typed': '''byte=(x:uint8)=>x as int64
main=()=>{const [a b]:array<uint8>=[20 22] return byte(a)+byte(b)}''',
    'unpack-const-global-once': '''let calls=0
make=()=>{calls+=1 return [[20] [22]]}
const [[left] [right]]:array<array<int64>>=make()
main=()=>if calls=?1 left+right else 1''',
    'unpack-const-global-discard': '''let calls=0
make=()=>{calls+=1 return [20 22]}
const [_ _]:array<int64>=make()
main=()=>calls+41''',
    'unpack-const-closure-copy': '''make=()=>{
let source=[[20 22]] const [saved]=source let read=()=>saved
source[0][0]=99 return read}
main=()=>{let read=make() let copy=read() copy[0]=0
return if read()=?[20 22] 42 else 1}''',
    'unpack-const-dictionary': '''main=()=>{
const [[key a] [_ b]]:dict<string int64>=["hi"->20 "bye"->20]
return a+b+key.length}''',
    'unpack-nested-array': 'main=()=>{let [[a b] [c d]]=[[20 1] [2 19]] return a+b+c+d}',
    'unpack-nested-single': 'main=()=>{let [[answer]]=[[42]] return answer}',
    'unpack-loop-single-array': 'main=()=>{let total=0 loop [x] in [[20] [22]] {total+=x} return total}',
    'unpack-loop-single-record': 'main=()=>{let total=0 loop [x] in [[x=20 y=1] [x=22 y=2]] {total+=x} return total}',
    'unpack-loop-single-nested': 'main=()=>{let total=0 loop [[x]] in [[[20]] [[22]]] {total+=x} return total}',
    'unpack-loop-single-combined': 'main=()=>{let total=0 loop i in [0..2) and [x] in [[20] [21]] {total+=i+x} return total}',
    'unpack-loop-single-comprehension': 'main=()=>{let values=[loop [x] in [[20] [22]] x] return values[0]+values[1]}',
    'unpack-loop-single-sequence': '''Rows:type=[values:array<array<int64>>]
len=(rows:Rows)=>rows.values.length
__index__=(rows:Rows i:int64)=>rows.values[i]
main=()=>{let total=0 loop [x] in Rows[[[20] [22]]] {total+=x} return total}''',
    'unpack-loop-array': '''main=()=>{let total:int64=0
loop [a b c] in [[1 2 3] [10 12 14]] {total+=a+b+c} return total}''',
    'unpack-loop-record': '''main=()=>{let total:int64=0
loop [x y] in [[x=20 y=1] [x=19 y=2]] {total+=x+y} return total}''',
    'unpack-loop-nested-map': '''main=()=>{let total:int64=0
let entries=["a"->[20 1] "b"->[2 19]]
loop [key [x y]] in entries {if key =? "a" or key =? "b" total+=x+y}
return total}''',
    'unpack-loop-nested-array': '''main=()=>{let total:int64=0
loop [[x y]] in [[[20 1]] [[2 19]]] {total+=x+y} return total}''',
    'unpack-loop-nested-copy': '''main=()=>{let entries=["a"->[[20 22] [99]]]
loop [key [first _]] in entries {first[0]=0 if first[1] not=? 22 return 1}
let value=entries.get("a") if value is? none return 2
return value[0][0]+value[0][1]}''',
    'unpack-loop-nested-combined': '''main=()=>{let total:int64=0
loop i in [0..3) and [[x y]] in [[[20 1]] [[2 19]] [[99 99]]] and i <? 2 {
total+=x+y if i =? 0 continue
}
return total}''',
    'unpack-loop-nested-else': '''main=()=>{let total:int64=0
let entries:dict<string array<int64>>=[]
loop [key [x y]] in entries {total+=x+y} else {total=42}
return total}''',
    'unpack-loop-nested-guard': '''main=()=>{let total:int64=0
let entries=["a"->[20 22] "b"->[1 2]]
loop [key [x y]] in entries and key =? "a" {total+=x+y} else {total=1}
return total}''',
    'unpack-loop-map-guard-else': '''main=()=>{let total:int64=0
let entries=["a"->1 "b"->2]
loop [key value] in entries and value <? 1 {total+=value} else {total=42}
loop key in entries and key =? "a" {total+=1}
return total-1}''',
    'unpack-loop-nested-sequence': '''Rows:type=[values:array<array<array<int64>>>]
len=(rows:Rows)=>rows.values.length
__index__=(rows:Rows i:int64)=>rows.values[i]
main=()=>{let total:int64=0
loop [[x y]] in Rows[[[[20 1]] [[2 19]]]] {total+=x+y} return total}''',
    'unpack-nested-implicit': 'main=()=>{[[x _] [y]]=[[20 99] [22]] return x+y}',
    'unpack-nested-swap': '''main=()=>{let x:int64=20 let y:int64=22
[[x] [y]]=[[y] [x]] return if x =? 22 and y =? 20 42 else 1}''',
    'unpack-nested-once': '''let calls:int64=0
make=()=>{calls+=1 return [[20] [22]]}
main=()=>{let [[x] [y]]=make() return if calls =? 1 x+y else 1}''',
    'unpack-nested-copy': '''main=()=>{let source=[[[20 22] [99]]]
let [[first _]]=source let snapshot=first first[0]=0
return if source[0][0][0] =? 20 and snapshot[0] =? 20 and first[1] =? 22 42 else 1}''',
    'unpack-nested-record': '''main=()=>{let source=[[x=20 y=1] [x=2 y=22]]
let [[x] [y]]=source return x+y}''',
    'unpack-nested-global': '''let calls:int64=0
make=()=>{calls+=1 return [[20] [22]]}
let [[x] [y]]=make()
main=()=>if calls =? 1 x+y else 1''',
    'unpack-nested-global-discard': '''let calls:int64=0
make=()=>{calls+=1 return [[20] [22]]}
let [[_] [_]]=make()
main=()=>calls+41''',
    'unpack-single': 'main=()=>{let [answer]=[42] return answer}',
    'unpack-many': 'main=()=>{let [a b c d e]=[2 4 6 10 20] return a+b+c+d+e}',
    'unpack-discard': '''main=()=>{let [first _ last]=["aa" "drop" "bbb"]
return first.length+last.length+37}''',
    'unpack-record': '''Point:type=[x:int64 y:int64 z:int64]
main=()=>{let [y x]=Point[20 22 99] return x+y}''',
    'unpack-record-copy': '''main=()=>{let original=[values=[20 22]] let [values]=original
values[0]=99 return original.values[0]+original.values[1]}''',
    'unpack-swap': '''main=()=>{let x:int64=20 let y:int64=22 [x y]=[y x]
return if x =? 22 and y =? 20 42 else 1}''',
    'unpack-record-assign': '''main=()=>{let x:int64=0 let y:int64=0 [y x]=[x=20 y=22]
return x+y}''',
    'unpack-implicit': 'main=()=>{[x y]=[20 22] return x+y}',
    'unpack-once': '''let calls:int64=0
make=()=>{calls+=1 return [x=20 y=22]}
main=()=>{let [x y]=make() return if calls =? 1 x+y else 1}''',
    'unpack-global': 'let [y x]=[x=20 y=22]\nmain=()=>x+y',
    'unpack-global-discard': '''let calls:int64=0
make=()=>{calls+=1 return [20 22]}
let [_ _]=make()
main=()=>calls+41''',
    'unpack-default-shadow': '''combine=(@x:int64 b:int64={let [x y]=[20 22] x+y})=>x+b
main=()=>{let x:int64=0 return combine(@x)}''',
    'arrays': '''main=():>int64=>{let a:array<int64>=[20 22] let b=a b[0]=0 return a[0]+a[1]}''',
    'array-slices': '''main=()=>{let xs:array<int64>=[10 20 22 99]
let a=xs[1..2] let b=xs[1..3) let c=xs[..1] let d=xs[2..] let e=xs[..]
let empty=xs[2..2) a[0]=0
return if b[0]+b[1] =? 42 and c.length =? 2 and d[0] =? 22 and e.length =? 4 and empty.length =? 0 and xs[1] =? 20 42 else 1}''',
    'comprehension-basic': '''main=()=>{let values=[loop i in [0..4) i*7]
let total:int64=0 loop value in values total+=value return total}''',
    'comprehension-filter': '''main=()=>{let values=[loop x in [10 20 12 99] if x <? 90 x]
return values[0]+values[1]+values[2]}''',
    'comprehension-branches': '''main=()=>{let values=[loop x in [1 2 3] if x =? 1 10 else if x =? 2 20 else 12]
return values[0]+values[1]+values[2]}''',
    'comprehension-nested-loop': '''main=()=>{let values=[loop x in [1 2] loop y in [3 4] x*y]
let total:int64=0 loop value in values total+=value return total*2}''',
    'comprehension-block': '''main=()=>{let values=[loop x in [10 11] {let twice=x*2 twice}]
return values[0]+values[1]}''',
    'comprehension-control': '''main=()=>{let values=[loop x in 0.. {if x =? 0 continue if x >? 3 break x*7}]
return values[0]+values[1]+values[2]}''',
    'comprehension-graphemes': '''main=()=>{let values=[loop i in 0.. and c in "é🙂a" i+c.length]
return (values[0]+values[1]+values[2])*7}''',
    'comprehension-records': '''main=()=>{let values=[loop x in [20 22] [value=x]]
return values[0].value+values[1].value}''',
    'comprehension-copy': '''main=()=>{let original=[[values=[20 22]]]
let copied=[loop item in original item] copied[0].values[0]=99
return original[0].values[0]+original[0].values[1]}''',
    'comprehension-dictionary': '''main=()=>{let values=[loop key in ["a" "b"] key->21]
return values["a"]+values["b"]}''',
    'comprehension-dictionary-zip': '''main=()=>{let values=["a"->20 "b"->22]
let scaled=[loop [key value] in values and factor in [2 3] key->value*factor]
return if scaled["a"] =? 40 and scaled["b"] =? 66 42 else 1}''',
    'comprehension-dictionary-update': '''main=()=>{let values=[loop x in [1 2] "same"->x]
return values["same"]+40}''',
    'comprehension-context': '''main=()=>{let values:array<uint8>=[loop i in [0..3) 14]
return (values[0] as int64)+(values[1] as int64)+(values[2] as int64)}''',
    'comprehension-argument': '''total=(values:array<uint8>)=>(values[0] as int64)+(values[1] as int64)+(values[2] as int64)
main=()=>total([loop i in [0..3) 14])''',
    'comprehension-nested-array': '''main=()=>{let values=[loop x in [10 11] [loop y in [1 1] x*y]]
return values[0][0]+values[0][1]+values[1][0]+values[1][1]}''',
    'comprehension-empty': '''main=()=>{let values:array<int64>=[loop i in [0..0) {}]
return values.length+42}''',
    'comprehension-match': '''main=()=>{let values=[loop x in [1 2] match x {<1>=>20 _=>22}]
return values[0]+values[1]}''',
    'comprehension-once': '''let calls:int64=0
items=()=>{calls+=1 return [20 22]}
main=()=>{let values=[loop x in items() x] return if calls =? 1 values[0]+values[1] else 1}''',
    'comprehension-statements': '''main=()=>{let total:int64=0
let values:array<int64>=[loop x in [20 22] {total+=x}]
return total+values.length}''',
    'comprehension-default': '''total=(a:int64 values:array<int64>=[loop i in [0..a) 14])=>{let result:int64=0
loop value in values result+=value return result}
main=()=>total(3)''',
    'default-reference-shadow-only': '''combine=(a:int64 b:int64={let a:int64=2 a})=>a+b
main=()=>combine(40)''',
    'default-reference-loop-shadow': '''total=(@i:int64 values:array<int64>=[loop i in [0..3) 14])=>{let result:int64=0
loop value in values result+=value return result+i}
main=()=>{let i:int64=0 return total(@i)}''',
    'slice-managed-elements': '''Item:type=[values:array<int64> name:string]
main=()=>{let a=[Item[[20 22] "answer"]] let b=a[..] b[0].values[0]=99
a.clear() return if b[0].name =? "answer" b[0].values[1]+20 else 1}''',
    'slice-bound-side-effect': '''let xs:array<int64>=[]
start=()=>{xs[0]=99 return 0}
main=()=>{xs.push(20) xs.push(22) let a=xs[start()..] return a[0]+a[1]}''',
    'slice-replaced-source': '''let xs:array<int64>=[]
start=()=>{xs=[] xs.push(99) xs.push(100) return 0}
main=()=>{xs.push(20) xs.push(22) let a=xs[start()..] return a[0]+a[1]}''',
    'branches-loops': '''main=():>int64=>{let i:int64=0 loop i <? 3 {i+=1} return if i =? 3 42 else 1}''',
    'place': '''bump=(@x:int64):>void=>{x+=2}
main=():>int64=>{let x:int64=40 bump(@x) return x}''',
    'value-parameter': '''bump=(xs:array<int64>):>int64=>{xs[0]=0 return xs[0]}
main=():>int64=>{let xs:array<int64>=[42] bump(xs); return xs[0]}''',
    'floor': '''main=():>int64=>if (-7)//3 =? -3 and (-7)%3 =? 2 and 7//(-3) =? -3 and 7%(-3) =? -2 42 else 1''',
    'float': '''Vector:type=[x:float64 y:float64]
main=():>int64=>{let v=Vector[1.25 2.5] return if v.x*2.0 =? v.y 42 else 1}''',
    'conversion-int-float': '''main=()=>{let i:int64=42 let u:uint64=18446744073709551615
return if (i as float64) =? 42.0 and ((-i) as float32) =? -42.0 and (u as float64) >? 1.8e19 42 else 1}''',
    'conversion-float-width': '''main=()=>{let x:float64=1.25 let narrow=x as float32
return if (narrow as float64) =? 1.25 and (1.25 as float32) =? narrow 42 else 1}''',
    'conversion-float-int': '''main=()=>{let a:float64=42.9 let high:float64=300 let low:float64=-200
return if (a as int64) =? 42 and (high as uint8) =? 255 and (low as int8) =? -128 and (low as uint64) =? 0 42 else 1}''',
    'conversion-float-limits': '''main=()=>{let zero:float64=0.0 let nan=zero/zero let infinity=1.0/zero
return if (nan as int64) =? 0 and (nan as uint64) =? 0 and (infinity as int64) =? 9223372036854775807 and (infinity as uint64) =? 18446744073709551615 and ((-infinity) as int64) =? -9223372036854775808 42 else 1}''',
    'float-division': '''divide=(x:float64 y:float64):>float64=>x/y
main=():>int64=>if divide(84.0 2.0) =? 42.0 42 else 1''',
    'inverted-comparisons': '''main=():>int64=>if 1 not=? 2 and 1 not>? 2 and 2.0 not<? 1.0 42 else 1''',
    'based-integers': 'main=()=>if 0x2A =? 42 and 0b101010 =? 42 and 0o52 =? 42 and 0d42 =? 42 42 else 1',
    'other-bases': 'main=()=>if 0t1120 =? 42 and 0q222 =? 42 and 0s110 =? 42 and 0z36 =? 42 42 else 1',
    'unsigned-literal': '''main=()=>{let x:uint64=0xffff_ffff_ffff_ffff
let y=18446744073709551615 return if x =? y and y >? 0 42 else 1}''',
    'unsigned-constant-math': '''main=()=>{let n=0xffffffffffffffff-1
return if n >? 0 and (0xffffffffffffffff >> 63) =? 1 and 0xffffffffffffffff >? 0 and 0xffffffffffffffff+1 =? 0 42 else 1}''',
    'signed-minimum': '''main=()=>{let x:int64=-9223372036854775808
return if x <? 0 and x+1 =? -9223372036854775807 42 else 1}''',
    'narrow-integers': '''main=()=>{let a:int8=-128 let b:uint8=0xff
let c:int16=-32768 let d:uint16=0xffff
return if (a as int64) =? -128 and (b as int64) =? 255 and (c as int64) =? -32768 and (d as int64) =? 65535 42 else 1}''',
    'scientific': '''main=()=>if 4.2e1 =? 42.0 and 420e-1 =? 42.0 and 4_200e-2 =? 42.0 and 42e+0 =? 42.0 42 else 1''',
    'unary-plus': 'positive=(x:int64)=>+x\nmain=()=>positive(42)',
    'panic-ended-search': '''find_value=(xs:array<int64> target:int64):>int64=>{loop x in xs {if x =? target return x} panic("missing")}
main=()=>find_value([20 42] 42)''',
    'grapheme-length': 'main=()=>if "".length =? 0 and "é👩‍👩‍👧‍👦🇺🇸".length =? 3 and "ASCII".length =? 5 and "\\r\\n".length =? 1 42 else 1',
    'grapheme-index': 'main=()=>{let s="Aé👩‍👩‍👧‍👦🇺🇸" return if s[1] =? "é" and s[2] =? "👩‍👩‍👧‍👦" and s[3] =? "🇺🇸" 42 else 1}',
    'grapheme-slices': '''main=()=>{let s="Aé👩‍👩‍👧‍👦🇺🇸"
return if s[1..2] =? "é👩‍👩‍👧‍👦" and s[1..3) =? "é👩‍👩‍👧‍👦" and s[..0] =? "A" and s[3..] =? "🇺🇸" and s[..] =? s and s[2..2) =? "" and s[4..] =? "" 42 else 1}''',
    'grapheme-loop': '''main=()=>{let s="é👩‍👩‍👧‍👦🇺🇸" let text="" let count:int64=0
loop cluster in s {text+=cluster count+=1}
return if text =? s and count =? 3 42 else 1}''',
    'grapheme-zipped-loop': '''main=()=>{let text="" let count:int64=0
loop a in "é👩‍👩‍👧‍👦🇺🇸" and b in "123" {if b =? "2" continue text+=a count+=1}
return if text =? "é🇺🇸" and count =? 2 42 else 1}''',
    'grapheme-bound-side-effect': '''let text="é👩‍👩‍👧‍👦"
start=()=>{text="replacement" return 1}
main=()=>{let part=text[start()..] return if part =? "👩‍👩‍👧‍👦" and text =? "replacement" 42 else 1}''',
    'binary-literals': '''main=()=>{let a=0x"ab_cd" let b=0b"101" let c=0q"123" let d=0o"123" let e=0u"v" let f=0g"aA=="
return if a.length =? 2 and a[0] =? 171 and a[1] =? 205 and b[0] =? 160 and c[0] =? 108 and d[0] =? 41 and d[1] =? 128 and e[0] =? 248 and f[0] =? 42 and f[1] =? 64 42 else 1}''',
    'utf8-decode': '''main=()=>{let text=0x"65cc81f09f9982" as string|none
let bad=0x"eda080" as string|none let empty=0x"" as string?
return if text is? string and text =? "é🙂" and text.length =? 2 and bad is? none and empty is? string and empty =? "" 42 else 1}''',
    'utf8-copy': '''main=()=>{let original="hé" let bytes=original as array<uint8>
let decoded=bytes as string|none bytes[0]=120 let again=original as array<uint8>
return if decoded is? string and decoded =? original and again[0] =? 104 and bytes[0] =? 120 42 else 1}''',
    'unicode': 'main=():>int64=>{let α:int64=42 printl"é🙂 {α}" return α}',
    'argv': 'main=(args:array<string>):>int64=>if args.length =? 2 42 else 1',
    'array-iteration': 'main=():>int64=>{let sum:int64=0 loop x in [20 22] {sum+=x} return sum}',
    'unit-range-limits': '''count=<T>(start:T end:T):>int64=>{
let result:int64=0
loop i in [start..end] {result+=1 if result >? 4 panic("range did not stop")}
return result
}
main=()=>{
let total:int64=0
 total+=count(125 as int8 127 as int8)
 total+=count(253 as uint8 255 as uint8)
 total+=count(32765 as int16 32767 as int16)
 total+=count(65533 as uint16 65535 as uint16)
 total+=count(2147483645 as int32 2147483647 as int32)
 total+=count(4294967293 as uint32 4294967295 as uint32)
 total+=count(9223372036854775805 9223372036854775807)
 total+=count(18446744073709551613 18446744073709551615)
let signed:array<int64>=[] let unsigned:array<uint64>=[]
let low:int64=-9223372036854775808
loop i in [low..9223372036854775807] {signed.push(i) if signed.length =? 3 break}
let zero:uint64=0
loop i in [zero..18446744073709551615] {unsigned.push(i) if unsigned.length =? 3 break}
return if total =? 24 and signed =? [low low+1 low+2]
and unsigned =? [zero zero+1 zero+2] 42 else 1
}''',
    'unit-range-combined-limits': '''count=<T>(start:T end:T):>int64=>{
let result:int64=0
loop i in [start..end] and j in [0..5) {result+=1 i=start if result >? 4 panic("range did not stop")}
return result
}
main=()=>{
let total=count(125 as int8 127 as int8)+count(253 as uint8 255 as uint8)
let high:int64=9223372036854775807 let top:uint64=18446744073709551615
 total+=count(high-2 high)+count(top-2 top)
let conditional:int64=0
loop i in [high-2..high] and i >=? 0 {conditional+=1}
return if total =? 12 and conditional =? 3 42 else 1
}''',
    'unit-range-combined-optional': '''main=()=>{
let top:uint8=255 let rows:int64=0 let missing:int64=0 let total:int64=0
loop i in [top..top] or x in [10 20 12] {
    rows+=1
    if rows >? 4 panic("range did not stay exhausted")
    if i is? none {missing+=1} else {if i not=? top return 1}
    if x isnt? none {total+=x}
}
let empty:int64=0
loop i in [top..top) or x in [1 2] {if i isnt? none return 2 empty+=1}
return if rows =? 3 and missing =? 2 and total =? 42 and empty =? 2 42 else 3
}''',
    'unit-range-combined-booleans': '''main=()=>{
let count:int64=0
loop count <? 2 or count <? 3 {count+=1}
let sum:int64=0
loop i in [0..10) and (i <? 2 or i =? 2) {sum+=i}
return if count =? 3 and sum =? 3 42 else 1
}''',
    'unit-range-combined-snapshots': '''main=()=>{
let numbers=[10 20] let text="á🙂!" let total:int64=0 let rows:int64=0 let letters:int64=0
loop number in numbers or character in text {
    rows+=1 numbers.clear() text=""
    if number isnt? none {total+=number}
    if character isnt? none {letters+=character.length}
}
let empty:array<int64>=[]
loop a in empty or b in empty {return 1}
return if rows =? 3 and total =? 30 and letters =? 3 42 else 2
}''',
    'unit-range-combined-shadow': '''main=()=>{
let value:int64=0 let count:int64=0
loop value =? 0 and value in [20 22] {count+=1}
loop value =? 0 and value in [1..2] {count+=1}
loop value =? 0 and value in [10 11] and i in 0.. {count+=1}
return if count =? 6 and value =? 0 42 else 1
}''',
    'unit-range-combined-order': '''let calls:int64=0
start=()=>{calls+=1 return 10}
main=()=>{
let values=[20 22] let sum:int64=0
loop i in start().. and x in values {sum+=i+x}
let high:uint8=255 let last:int64=0
loop x in [1] and i in high.. {last=i as int64}
return if sum =? 63 and calls =? 1 and last =? 255 42 else 1
}''',
    'unit-range-order': '''let order:int64=0
bound=(tag:int64 value:int64)=>{order=order*10+tag return value}
main=()=>{
let count:int64=0
loop i in [bound(1 9223372036854775805)..bound(2 9223372036854775807)] {
    i=0 count+=1 continue
}
let start:uint8=255
loop i in [start..] {if i not=? 255 return 1 break}
return if count =? 3 and order =? 12 42 else 2
}''',
    'stepped-range-values': '''main=()=>{
let up:array<int64>=[] let down:array<int64>=[] let open:array<int64>=[]
loop i in [0,2..8] {up.push(i)}
loop i in [8,5..0) {down.push(i)}
loop i in [1,4..] {if i >? 10 break if i =? 4 continue open.push(i)}
let empty:int64=0
loop i in [10,12..0] {empty+=1}
loop i in [0,-2..10] {empty+=1}
let collected=[loop i in [1,3..8] i*2]
return if up =? [0 2 4 6 8] and down =? [8 5 2] and open =? [1 7 10]
and empty =? 0 and collected =? [2 6 10 14] 42 else 1
}''',
    'stepped-range-managed': '''main=()=>{
let values=[loop i in [0..8) [amount=i]] let saved=values
loop i in [0,2..6] {values[i].amount+=10}
let sum:int64=0
loop i in [7,5..0] {sum+=values[i].amount}
return if sum =? 16 and values[0].amount =? 10 and values[6].amount =? 16
and saved[0].amount =? 0 and saved[6].amount =? 6 42 else 1
}''',
    'stepped-range-array-paths': '''change=(@values:array<int64>):>void=>{
loop pass in [0..3) {loop i in [0,3..values.length) {values[i]+=2}}
}
main=()=>{
let values=[loop i in [0..10) i] let saved=values
change(@values)
let record=[values=[10 20 30 40]] let record_saved=record
loop i in [1,3..record.values.length) {record.values[i]+=2}
let length=values.length let sum:int64=0
loop i in [0,3..length) {sum+=values[i]}
let empty:array<int64>=[]
loop i in [0,3..empty.length) {return empty[i]}
return if sum =? 42 and saved =? [0 1 2 3 4 5 6 7 8 9]
and record.values =? [10 22 30 42] and record_saved.values =? [10 20 30 40] 42 else 1
}''',
    'stepped-range-nested-indices': '''main=()=>{
let values=[10 20 30 40] let sum:int64=0
loop i in [0,2..values.length) {
    loop j in [1,3..values.length) {sum+=values[i]+values[j]}
}
let replacement:int64=0
loop i in [0,2..values.length) {i=1 replacement+=values[i]}
return if sum =? 200 and replacement =? 40 42 else 1
}''',
    'stepped-range-open-combined': """main=()=>{
let a:array<int64>=[] let b:array<int64>=[]
loop i in [0,2..] and x in [10 20 30] {a.push(i+x)}
loop x in [10 20 30] and i in [6,3..] {b.push(i+x)}
return if a=?[10 22 34] and b=?[16 23 30] 42 else 1
}""",
    'stepped-range-open-control': """main=()=>{
let a:array<int64>=[]
loop i in [1,3..] and i<?10 {if i=?5 continue a.push(i) if i=?7 break}
let b=[loop i in [2,4..] and x in [10 20 30] i+x]
return if a=?[1 3 7] and b=?[12 24 36] 42 else 1
}""",
    'stepped-range-open-order': """let trace:int64=0
bound=(tag:int64 value:int64)=>{trace=trace*10+tag return value}
main=()=>{
let a:array<int64>=[]
loop i in [bound(1 8),bound(2 5)..] and x in [bound(3 10) bound(4 20)] {a.push(i+x)}
let entered=false
loop i in [1,3..] and x in ([] as array<int64>) {return 1} else {entered=true}
return if trace=?1234 and a=?[18 25] and entered 42 else 1
}""",
    'stepped-range-open-or': """main=()=>{
let a:array<int64>=[] let b:array<int64>=[]
loop i in [0,2..] or x in [10 20] {
    a.push(i??-1) b.push(x??-1)
    if a.length=?4 break
}
return if a=?[0 2 4 6] and b=?[10 20 -1 -1] 42 else 1
}""",
    'stepped-range-open-extremes': """main=()=>{
let a:array<int64>=[] let b:array<int64>=[]
loop i in [int64.min,int64.max..] and n in [0 1] {a.push(i) if n=?1 break}
loop i in [int64.max,int64.min..] and n in [0 1] {b.push(i) if n=?1 break}
return if a=?[int64.min int64.max] and b=?[int64.max int64.min] 42 else 1
}""",
    'stepped-range-order': '''let order:int64=0
bound=(tag:int64 value:int64):>int64=>{order=order*10+tag return value}
main=()=>{let values:array<int64>=[]
loop i in [bound(1 1),bound(2 4)..bound(3 10)] {values.push(i) i=99}
return if order =? 123 and values =? [1 4 7 10] 42 else 1}''',
    'stepped-range-widths': '''main=()=>{
let low:int8=-128 let second:int8=0 let high:int8=127
let signed:array<int64>=[]
loop i in [low,second..high] {signed.push(i as int64)}
let a:uint8=255 let b:uint8=253 let end:uint8=249
let unsigned:array<int64>=[]
loop i in [a,b..end] {unsigned.push(i as int64)}
return if signed =? [-128 0] and unsigned =? [255 253 251 249] 42 else 1
}''',
    'stepped-range-limits': '''main=()=>{
let low:int64=-9223372036854775808 let high:int64=9223372036854775807
let top:uint64=18446744073709551615 let zero:uint64=0
let a:array<int64>=[] let b:array<int64>=[] let c:array<uint64>=[] let d:array<uint64>=[]
loop i in [low,high..high] {a.push(i) if a.length >? 3 break}
loop i in [high,low..low] {b.push(i) if b.length >? 3 break}
loop i in [zero,top..top] {c.push(i) if c.length >? 3 break}
loop i in [top,zero..zero] {d.push(i) if d.length >? 3 break}
let signed_prefix:array<int64>=[] let unsigned_prefix:array<uint64>=[]
loop i in [low,low+1..high] {signed_prefix.push(i) if signed_prefix.length =? 3 break}
loop i in [zero,zero+1..top] {unsigned_prefix.push(i) if unsigned_prefix.length =? 3 break}
return if a =? [low high] and b =? [high low] and c =? [zero top] and d =? [top zero]
and signed_prefix =? [low low+1 low+2] and unsigned_prefix =? [zero zero+1 zero+2] 42 else 1
}''',
    'range-ends': '''main=():>int64=>{let sum:int64=0 loop i in 0..3 {sum+=i}
loop i in [0..3) {sum+=i} loop i in [0..3] {sum+=i} return sum+27}''',
    'combined-continue': '''main=():>int64=>{let sum:int64=0
loop i in 0.. and i <? 8 {if i =? 3 continue if i =? 6 break sum+=i} return sum+30}''',
    'zipped-continue': '''main=():>int64=>{let sum:int64=0
loop x in [10 20 12] and i in 0.. {if i =? 1 continue sum+=x} return sum+20}''',
    'nested-combined': '''main=():>int64=>{let sum:int64=0
loop i in 0.. and i <? 3 {loop j in 0.. and j <? 2 {sum+=7}} return sum}''',
}
ERRORS = {
    'closure-shared-duplicate': ('main=()=>{let n=0 let f=($capture @n $capture @n)=>n return f()}', 'duplicate parameter binding'),
    'closure-capture-mixed-duplicate': ('main=()=>{let n=0 let f=($capture n $capture @n)=>n return f()}', 'duplicate parameter binding'),
    'closure-capture-parameter-conflict': ('main=()=>{let n=0 let f=($capture @n n:int64)=>n return f(1)}', 'duplicate parameter binding'),
    'closure-capture-parameter-conflict-reversed': ('main=()=>{let n=0 let f=(n:int64 $capture @n)=>n return f(1)}', 'duplicate parameter binding'),
    'closure-capture-unpack-conflict': ('main=()=>{let n=0 let f=($capture @n [n x])=>n+x return f([1 2])}', 'duplicate parameter binding'),
    'closure-capture-missing-name': ('main=()=>{let f=($capture)=>1 return f()}', '$capture without a local name'),
    'closure-capture-repeated-tag': ('main=()=>{let n=0 let f=($capture $capture @n)=>n return f()}', '$capture without a local name'),
    'closure-capture-unknown-tag': ('main=()=>{let n=0 let f=($captur @n)=>n return f()}', 'parameter modifier'),
    'closure-capture-module': ('f=($capture n)=>n\nmain=()=>f()', '$capture on a module function'),
    'closure-capture-underscore': ('main=()=>{let f=($capture _)=>1 return f()}', 'a capture other than an enclosing local name'),
    'closure-capture-old-list': ('main=()=>{let n=0 let f=[@n]()=>n return f()}', 'use ($capture @name)'),
    'closure-shared-field': ('main=()=>{let r=[n=0] let f=($capture @r.n)=>r.n return f()}', 'a capture other than an enclosing local name'),
    'closure-shared-global': ('let n=0\nmain=()=>{let f=($capture @n)=>n return f()}', 'a capture must name an enclosing local'),
    'closure-capture-global-value': ('let n=0\nmain=()=>{let f=($capture n)=>n return f()}', 'a capture must name an enclosing local'),
    'closure-capture-const': ('main=()=>{const xs=[0] let f=($capture xs)=>{xs[0]+=1; xs[0]} return f()}', 'cannot modify const'),
    'closure-capture-const-global': ('const n=0\nmain=()=>{let f=($capture n)=>n return f()}', 'a capture must name an enclosing local'),
    'closure-shared-parameter': ('make=(@n:int64)=>($capture @n)=>n\nmain=()=>{let n=0 let f=make(@n) return f()}', 'only variables declared with'),
    'closure-private-function-cycle': ('Counter:type=():>int64\nmain=()=>{let f:Counter=()=>0 let outer=()=>{let g=($capture @f)=>f() f=g return f()} return outer()}', 'keep it alive forever'),
    'closure-shared-function-cycle': ('Counter:type=():>int64\nmain=()=>{let f:Counter=()=>0 let g=($capture @f)=>f() f=g return 42}', 'keep it alive forever'),
    'sequence-mutable-value-write': ('main=()=>{let xs=[1] loop x in xs x+=1}', '`loop @item`'),
    'sequence-mutable-const': ('main=()=>{const xs=[1] loop @x in xs x+=1}', 'cannot modify const'),
    'sequence-mutable-range': ('main=()=>{let xs=[0..2) loop @x in xs x+=1}', 'needs stored array elements'),
    'sequence-mutable-string': ('main=()=>{let xs="abc" loop @x in xs printl(x)}', 'needs stored array elements'),
    'sequence-mutable-dict': ('main=()=>{let xs=[1->2] loop @x in xs x+=1}', 'needs stored array elements'),
    'sequence-mutable-custom': ('Series:type=[count:int64]\nlen=(s:Series)=>s.count\n__index__=(s:Series i:int64)=>i\nmain=()=>{let xs=Series[2] loop @x in xs x+=1}', 'needs stored array elements'),
    'sequence-mutable-call': ('items=()=>[1]\nmain=()=>{loop @x in items() x+=1}', 'use an array binding'),
    'sequence-mutable-index': ('main=()=>{let xs=[[1]] loop @x in xs[0] x+=1}', 'use an array binding'),
    'sequence-mutable-slice': ('main=()=>{let xs=[1] loop @x in xs[..] x+=1}', 'use an array binding'),
    'sequence-mutable-combined': ('main=()=>{let xs=[1] loop @x in xs and x<?2 x+=1}', 'mutable binding in a combined loop'),
    'sequence-mutable-pattern': ('main=()=>{let xs=[[1]] loop @[x] in xs x+=1}', 'unpacking a mutable loop binding'),
    'sequence-mutable-push': ('main=()=>{let xs=[1] loop @x in xs {xs.push(2) x+=1}}', '`loop @item` changes the elements'),
    'sequence-mutable-replace': ('main=()=>{let xs=[1] loop @x in xs {xs=[2] x+=1}}', '`loop @item` changes the elements'),
    'sequence-mutable-parent': ('Box:type=[xs:array<int64>]\nmain=()=>{let box=Box[[1]] loop @x in box.xs {box=Box[[2]] x+=1}}', '`loop @item` changes the elements'),
    'sequence-mutable-global-call': ('let xs=[1]\ngrow=()=>xs.push(2)\nmain=()=>{loop @x in xs {grow() x+=1}}', '`loop @item` changes the elements'),
    'sequence-mutable-escape': ('main=()=>{let xs=[1] loop @x in xs {let later=($capture @x)=>{x+=1} later()}}', 'stands for an element only while the loop is there'),
    'numeric-broadcast-update-constant': ('main=()=>{const xs=[1 2] xs .+= 1 return 0}', 'constant'),
    'numeric-broadcast-selection-constant': ('main=()=>{const xs=[1 2] xs[..] .+= 1 return 0}', 'constant'),
    'numeric-broadcast-selection-mask-constant': ('main=()=>{const xs=[1 2] xs[[true false]] .+= 1 return 0}', 'constant'),
    'numeric-broadcast-matrix-selection-constant': ('main=()=>{const m=zeros(2 3) m[[..] 1] .+= 1.0 return 0}', 'constant'),
    'gpu-array-cpu-input': ('main=()=>{printl(cpu(gpu([1.0 2.0]) .+ [3.0 4.0]))}',
                            'this array is in CPU memory'),
    'gpu-array-exact-division': ('main=()=>{printl(cpu(gpu([1 2]) ./ 2))}',
                                 'GPU array expressions must return a fixed-width integer, float or bool, found Rational'),
    'gpu-array-managed-result': ('word=(x:float32)=>"value"\nmain=()=>{printl(cpu(word.(gpu([1.0]))))}',
                                 'GPU array expressions must return a fixed-width integer, float or bool'),
    'gpu-array-capture': (('main=()=>{let offset=float32(1.0) let shift=(x:float32)=>x+offset '
                           'printl(cpu(shift.(gpu([1.0 2.0]))))}'),
                          'captures variables cannot run on the GPU'),
    'unpack-leaf-narrow': ('main=()=>{let [x:uint8]=[42] return x}', 'cannot implicitly convert int to u8'),
    'unpack-leaf-incompatible': ('main=()=>{let [x:string]=[42] return 42}', 'expected str, found int'),
    'unpack-leaf-discard-incompatible': ('main=()=>{let [_:string]=[42] return 42}', 'expected str, found int'),
    'unpack-leaf-constant-write': ('main=()=>{const [x:int64]=[20] x=42 return x}', 'cannot modify const'),
    'unpack-leaf-reassignment': ('main=()=>{let x=20 [x:int64]=[42] return x}', 'type annotations declare bindings'),
    'unpack-leaf-duplicate': ('main=()=>{let [x:int64 x:float64]=[20 22] return x}', 'duplicate unpacking name'),
    'unpack-leaf-nested-annotation': ('main=()=>{let [[x]:array<int64>]=[[42]] return x}', 'annotated nested pattern'),
    'generic-constructor-narrow-overflow': ('Batch:type=<T>[items:array<T> exemplar:T]\nmain=()=>{let b=Batch([256] (0 as uint8)) return 42}', 'does not fit in u8'),
    'generic-constructor-conflicting-elements': ('Pair:type=<T>[left:array<T> right:array<T>]\nmain=()=>{let p=Pair([20] ["bad"]) return 42}', 'expected int, found str'),
    'generic-constructor-unresolved-empty': ('Box:type=<T>[value:T]\nmain=()=>{let box=Box([]) return box.value.length}', "cannot infer the type of 'box'"),
    'generic-constructor-conflicting-callback': ('Runner:type=<T>[value:T step:((x:T):>T)]\nmain=()=>{let r=Runner(42 (x:string)=>x) return 42}', 'parameter type str does not match expected int'),
    'fixed-array-wrong-length': ('main=()=>{let values:array<int64 length=2>=[1 2 3] return 42}', '2 elements'),
    'fixed-array-unpack-length': ('main=()=>{let values:array<int64 length=2>=[20 22] let [a b c]=values return 42}', 'exactly 3 elements'),
    'fixed-array-zero-length': ('main=()=>{let values:array<int64 length=0>=[] return 42}', 'at least 1'),
    'fixed-array-compound-slice': ('main=()=>{let xs:array<int64 length=2>=[20 22] xs[..]+=1 return 42}', 'compound assignment to picked elements'),
    'fixed-array-grow': ('main=()=>{let values:array<int64 length=2>=[20 22] values.push(0) return 42}', 'fixed size'),
    'fixed-array-mutable-conversion': ('change=(@xs:array<int64 length=2>)=>{xs[0]=42}\nmain=()=>{let xs=[20 22] change(@xs) return 42}', 'exact match'),
    'fixed-array-unknown-constraint': ('main=()=>{let values:array<int64 capacity=2>=[20 22] return 42}', 'length=N'),
    'record-spread-set': ('main=()=>{let values=set[1] let record=[values... answer=42] return 42}', 'only records can be spread into a record'),
    'set-spread-wrong-type': ('main=()=>{let values:array<uint8>=[set["wrong"]...] return 42}', 'u8'),
    'record-spread-array': ('main=()=>{let xs=[1] let record=[xs... answer=42] return 42}', 'only records can be spread into a record'),
    'record-spread-unnamed': ('main=()=>{let base=[answer=42] let record=[base... 1] return 42}', 'a record literal needs named fields or record spreads'),
    'generic-value-ambiguous': ('choose=<T>(x:T):>T=>x\nchoose=<T>(x:T y:T):>T=>y\nmain=()=>{let f=choose<int64> return 42}', 'multiple versions of'),
    'generic-value-wrong-type-count': ('identity=<T>(x:T):>T=>x\nmain=()=>{let f=identity<int64 string> return 42}', 'no version of'),
    'generic-value-conflicting-type': ('identity=<T>(x:T):>T=>x\nmain=()=>{let f:((x:string):>string)=identity<int64> return 42}', 'no version of'),
    'spread-outside-literal': ('main=()=>{let xs=[42] return xs...}', 'spread is supported inside array or record literals'),
    'spread-call-argument': ('f=(x:int64)=>x\nmain=()=>f([42]...)', 'spread is supported inside array or record literals'),
    'end-index-call': ('main=()=>{let xs=[42] return xs[end()]}', 'end is the last index inside brackets; it cannot be called'),
    'end-index-outside': ('main=()=>end', "unknown name 'end'"),
    'numeric-bound-float': ('main=()=>float64.max', "type has no member 'max'"),
    'numeric-bound-unknown': ('main=()=>uint8.maximum', "type has no member 'maximum'"),
    'range-index-stepped-string': ('main=()=>"abc"[0,2..2].length', 'stepped slicing requires an array'),
    'coalesce-nonoptional': ('main=()=>42??0', 'needs an optional on the left'),
    'compound-integer-exact-division': ('main=()=>{let x=42 x/=2 return x}', 'expected int, found Rational'),
    'loop-else-value': ('main=()=>{let x=loop false {1} else 42 return x}', 'loop used as a value'),
    'loop-else-binder-scope': ('main=()=>{loop x in [0..0) {} else {return x} return 42}', "unknown name 'x'"),
    'loop-else-label-scope': ('main=()=>{$outer loop false {} else {break $outer} return 42}', 'outside of a loop'),
    'loop-else-break-fallthrough': ('main=()=>{loop true {if true {break} return 42} else {return 42}}', 'must return a value'),
    'loop-else-continue-fallthrough': ('main=()=>{loop i in [0..1) {continue} else {return 42}}', 'must return a value'),
    'loop-else-argument-exit': ('main=()=>{loop true {return {break; 42}} else {return 42}}', 'must return a value'),
    'loop-else-closure-return': ('main=()=>{loop i in [0..1) {let f=()=>42 f()} else {return 42}}', 'must return a value'),
    'loop-label-missing': ('main=()=>{loop true {break $missing}}', 'unknown loop label'),
    'loop-label-duplicate': ('main=()=>{$again loop true {$again loop true {break $again}}}', 'duplicate active loop label'),
    'loop-label-dangling': ('main=()=>{$again}', 'label must be followed by a loop'),
    'loop-label-non-loop': ('main=()=>{$again let x=42 return x}', 'label must be followed by a loop'),
    'loop-label-out-of-scope': ('main=()=>{$again loop false {} loop true {break $again}}', 'unknown loop label'),
    'loop-label-closure': ('main=()=>{$again loop true {let f=()=>{loop true {break $again}} f() break}}', 'unknown loop label'),
    'array-comparison-negative': ('main=()=>{let values:array<uint8>=[1] return values =? [-1]}', 'does not fit in u8'),
    'array-comparison-overflow': ('main=()=>{let values:array<uint8>=[1] return [256] =? values}', 'does not fit in u8'),
    'array-comparison-narrow-variable': ('main=()=>{let values:array<uint8>=[1] let other:int64=1 return values =? [other]}', 'cannot implicitly convert'),
    'array-comparison-different-arrays': ('main=()=>{let values:array<uint8>=[1] let other=[1] return values =? other}', 'cannot compare'),
    'constant-assign': ('value=()=>40\nmain=()=>{const x=value() x=42 return x}', 'cannot modify const'),
    'constant-unpack-write': ('main=()=>{const [a b]=[20 22] a=99 return a+b}', 'cannot modify const'),
    'constant-unpack-nested-write': ('main=()=>{const [[a]]=[[[20 22]]] a[0]=99 return 42}', 'cannot modify const'),
    'constant-unpack-global-write': ('const [a b]=[20 22]\nmain=()=>{b=99 return a+b}', 'cannot modify const'),
    'constant-unpack-captured-write': ('main=()=>{const [a]=[20] let change=()=>{a+=1} change() return 42}', 'cannot modify const'),
    'constant-unpack-mutable-argument': ('bump=(@x:int64)=>{x+=2}\nmain=()=>{const [a]=[40] bump(@a) return a}', 'cannot modify const'),
    'unpack-type-mismatch': ('main=()=>{let [a b]:array<uint8>=[256 0] return 42}', 'u8'),
    'constant-literal-assign': ('main=()=>{const x=40 x=42 return x}', 'cannot modify const'),
    'constant-array-write': ('main=()=>{const xs=[20 22] xs[0]=99 return 42}', 'cannot modify const'),
    'constant-map-write': ('main=()=>{const xs=["a"->20] xs["b"]=22 return 42}', 'cannot modify const'),
    'constant-field-write': ('main=()=>{const x=[value=20] x.value=42 return 42}', 'cannot modify const'),
    'constant-mutable-argument': ('bump=(@x:int64)=>{x+=2}\nvalue=()=>40\nmain=()=>{const x=value() bump(@x) return x}', 'cannot modify const'),
    'constant-captured-write': ('main=()=>{const xs=[20 22] let change=()=>{xs[0]=99} change() return 42}', 'cannot modify const'),
    'constant-global-write': ('const xs=[20 22]\nmain=()=>{xs.push(99) return 42}', 'cannot modify const'),
    'constant-narrowed-write': ('make=():>array<int64>|none=>[20 22]\nmain=()=>{const xs=make() if xs is? none return 1 xs[0]=99 return 42}', 'cannot modify const'),
    'constant-global-narrowed-write': ('make=():>array<int64>|none=>[20 22]\nconst xs=make()\nmain=()=>{if xs is? none return 1 xs[0]=99 return 42}', 'cannot modify const'),
    'constant-callable-write': ('main=()=>{const next=()=>40 next=()=>42 return next()}', 'cannot modify const'),
    'constant-no-initializer': ('main=()=>{const x:int64 return 42}', 'const declaration without an initializer'),
    'constant-runtime-length': ('width=()=>2\nmain=()=>{const n=width() let values:array<int64 length=n>=[20 22] return 42}', 'not a compile-time constant'),
    'combined-or-condition': ('main=()=>{loop i in [0..3) or true {printl(i)}}', 'only loop variables'),
    'stepped-range-arity': ('main=()=>{loop i in [0,1,2..5] {printl(i)}}', 'exactly two starting values'),
    'stored-range-open': ('main=()=>{let r=[0..] return 0}', 'stored range needs both endpoints'),
    'stored-range-no-start': ('main=()=>{let r=[..4] return 0}', 'stored range needs both endpoints'),
    'array-context-narrow-overflow': ('accept=(xs:array<uint8>)=>0\nmain=()=>accept([256])', 'expects u8[]'),
    'array-context-negative-unsigned': ('accept=(xs:array<uint64>)=>0\nmain=()=>accept([-1])', 'expects u64[]'),
    'numeric-array-unsigned-negative': ('main=()=>{let values=[-1 18446744073709551615] return 42}', 'does not fit in u64'),
    'array-context-variable-container': ('accept=(xs:array<uint64>)=>0\nmain=()=>{let xs=[42] return accept(xs)}', 'expects u64[]'),
    'array-context-variable-element': ('accept=(xs:array<uint8>)=>0\nmain=()=>{let x:int64=42 return accept([x])}', 'expects u8[]'),
    'bigint-literal-user-record': ('BigInt:type=[value:int64]\nmain=()=>{let value:BigInt=42 0}', 'type mismatch'),
    'bigint-literal-word-variable': ('from bigint import BigInt\nmain=()=>{let word:int64=42 let value:BigInt=word 0}', 'type mismatch'),
    'overload-group-value': ('choose=(()=>42)&42\nmain=()=>choose()', 'overload group member other than a function literal'),
    'overload-group-local': ('main=()=>{let choose=(()=>40)&((n:int64)=>n) return choose()+choose(2)}', 'local overload group'),
    'power-missing-protocol': ('Box:type=[value:int64]\nmain=()=>Box[2]^3', 'operator ^ is not defined'),
    'overload-group-main': ('main=(()=>42)&((n:int64)=>n)', 'overloaded entry point'),
    'main-record-result': ('main=()=>[value=42]', 'main must return void or an integer exit code'),
    'main-float-result': ('main=()=>42.5', 'main must return void or an integer exit code'),
    'operator-comparison-result': ('Box:type=[value:int64]\n__lt__=(a:Box b:Box)=>a.value-b.value\nmain=()=>Box[1] <? Box[2]', 'must return bool'),
    'named-duplicate': ('add=(x:int64 y:int64)=>x+y\nmain=()=>add(40 x=2)', 'given twice'),
    'match-union-subset-incomplete': ('pick=(v:int64|string|bool)=>match v {<int64|string>=>42}\nmain=()=>pick(0)', 'no arm for'),
    'match-union-subset-wrong-type': ('pick=(v:int64|string|bool)=>match v {<int64|float64>=>0 _=>42}\nmain=()=>pick(42)', 'not a member'),
    'match-union-literal-incomplete': ('pick=(v:int64|string)=>match v {<0>=>42 <string>=>0}\nmain=()=>pick(0)', 'no arm for'),
    'match-union-bool-incomplete': ('pick=(v:bool|string)=>match v {<true>=>42 <string>=>0}\nmain=()=>pick(true)', 'no arm for'),
    'match-union-literal-wrong-type': ('pick=(v:int64|bool)=>match v {<"no">=>0 _=>42}\nmain=()=>pick(42)', 'not a member'),
    'match-union-literal-overflow': ('pick=(v:uint8|string)=>match v {<256>=>0 _=>42}\nmain=()=>pick(42)', 'does not fit'),
    'match-union-partial-not-narrowed': ('pick=(v:int64|string)=>match v {<0>=>0 _=>v.length}\nmain=()=>pick(42)', 'length'),
    'match-incomplete': ('main=()=>match 42 {<42>=>42}', 'not exhaustive'),
    'match-incomplete-statement': ('main=()=>{match true {<true>=>42} return 42}', 'not exhaustive'),
    'match-wrong-type': ('main=()=>match 42 {n:string=>n.length _=>42}', 'not a member'),
    'match-refinement': ('main=()=>match 42 {n:int64<n >? 0>=>n _=>0}', 'does not yet support'),
    'missing-place': ('bump=(@x:int64):>void=>{x+=2}\nmain=():>int64=>{let x:int64=40 bump(x) return x}', 'needs `@`'),
    'unbounded-int': ('main=():>int=>42', 'unbounded integer'),
    'integer-division': ('main=():>int64=>85/2', 'type mismatch'),
    'literal-too-large': ('main=():>uint64=>18446744073709551616', 'type mismatch'),
    'hex-too-large': ('main=():>uint64=>0x10000000000000000', 'type mismatch'),
    'negative-too-large': ('main=():>int64=>-9223372036854775809', 'type mismatch'),
    'signed-literal-overflow': ('main=():>int64=>0xffffffffffffffff', 'does not fit'),
    'narrow-literal-overflow': ('main=()=>{let x:uint8=256 return x}', 'does not fit'),
    'float-literal-overflow': ('main=()=>1e309', 'exceeds float64'),
    'unary-plus-text': ('main=()=>+"text"', "needs a number"),
    'numeric-broadcast-unary-plus-text': ('main=()=>.+["text"]', 'needs a number'),
    'numeric-broadcast-unary-minus-text': ('main=()=>.-["text"]', 'cannot negate'),
    'reserved-binary-base': ('main=()=>0d"123"', 'based-string packing'),
    'binary-padding': ('main=()=>0g"=a"', 'padding'),
    'missing-asset': ('main=()=>{$include_bytes(p"missing.bin") as bytes return bytes.length}', 'cannot read'),
    'proof-directive': ('$assert true\nmain=():>int64=>42', 'does not yet support'),
    'effect-contract': ('main=():>int64 & no_effects=>42', 'does not yet support'),
    'missing-name': ('# 🙂\nmain=():>int64=>missing', 'unknown'),
    'default-reference-mutable': ('f=(@a:int64 b:int64=a)=>b\nmain=()=>{let a:int64=42 return f(@a)}', 'supply those defaults explicitly'),
    'record-duplicate': ('main=()=>{let value=[x=1 x=2] return 0}', 'duplicate record field'),
    'record-unknown-field': ('Value:type=[x:int64]\nmain=()=>{let v:Value=[y=42] return 0}', 'unknown'),
    'record-mixed-elements': ('main=()=>{let v=[x=42 2] return 0}', 'record item'),
    'record-untyped-empty-array': ('main=()=>{let v=[items=[]] return 0}', 'type annotation'),
    'record-inline-duplicate': ('main=()=>{let v:[x:int64 x:int64]=[] return 0}', 'duplicate record field'),
    'record-inline-default': ('main=()=>{let v:[x:int64=42]=[] return 0}', 'named record for defaults'),
    'record-inline-void': ('main=()=>{let v:[x:void]=[] return 0}', 'value types'),
    'record-inline-mutable-field': ('main=()=>{let v:[@x:int64]=[] return 0}', 'mutability belongs on the parameter'),
    'comprehension-mixed': ('main=()=>[loop i in [1 2] if i =? 1 "a"->2 else 3]', 'cannot mix'),
    'unpack-param-duplicate': ('sum=([x y] x)=>x+y\nmain=()=>sum([20 22] 0)', 'duplicate parameter binding'),
    'unpack-param-nested-duplicate': ('sum=([[x] [x]])=>x\nmain=()=>sum([[20] [22]])', 'duplicate unpacking name'),
    'unpack-param-mutable': ('sum=(@[x y]:array<int64>)=>x+y\nmain=()=>{let xs=[20 22] return sum(@xs)}', 'unpacking a mutable parameter'),
    'unpack-param-missing-field': ('sum=([missing])=>missing\nmain=()=>sum([x=42])', 'no field'),
    'unpack-loop-single-scalar': ('main=()=>{loop [x] in [42] {printl(x)} return 0}', 'found int'),
    'unpack-duplicate': ('main=()=>{let [x x]=[20 22] return x}', 'duplicate unpacking name'),
    'unpack-missing-field': ('main=()=>{let [missing]=[x=42] return missing}', 'no field'),
    'unpack-record-discard': ('main=()=>{let [_]=[x=42] return 0}', 'leave unwanted fields out'),
    'unpack-nested-scalar': ('main=()=>{let [[x]]=[42] return x}', 'unpacking needs an array, tuple, dictionary or record'),
    'unpack-nested-duplicate': ('main=()=>{let [[x] [x]]=[[20] [22]] return x}', 'duplicate unpacking name'),
    'unpack-nested-record-position': ('main=()=>{let [[x]]=[value=[42]] return x}', 'record unpacking needs field names'),
    'unpack-nested-empty': ('main=()=>{let [[]]=[[42]] return 0}', 'empty unpacking target'),
    'unpack-loop-duplicate': ('main=()=>{loop [x [x]] in [[1 2]] {} return 0}', 'duplicate unpacking name'),
    'set-empty-untyped': ('main=()=>{let values=set[] return 0}', 'cannot infer the type of an empty set'),
    'set-literal-range': ('main=()=>{let values:set<uint8>=set[256] return 0}', 'does not fit in u8'),
    'syntax-unicode-short': ('main=()=>"\\u123"', 'Unicode escape'),
    'syntax-unicode-bad-digit': ('main=()=>"\\u12G4"', 'hexadecimal'),
    'syntax-unicode-empty': ('main=()=>"\\u{}"', 'hex digits'),
    'syntax-unicode-surrogate': ('main=()=>"\\uD800"', 'scalar value'),
    'syntax-unicode-low-surrogate': ('main=()=>"\\u{DFFF}"', 'scalar value'),
    'syntax-unicode-range': ('main=()=>"\\u{110000}"', 'scalar value'),
    'syntax-unicode-huge': ('main=()=>"\\u{FFFFFFFFFFFFFFFFFFFF}"', 'too many digits'),
    'syntax-unicode-expression': ('main=()=>"\\u{41+1}"', 'hexadecimal'),
    'syntax-raw-unterminated': ('main=()=>r"missing', 'unterminated string'),
    'syntax-triple-unterminated': ('main=()=>"""missing', 'unterminated string'),
    'membership-return-type': ('Box:type=[value:int64]\ncontains=(box:Box value:int64)=>42\nmain=()=>1 in? Box[1]', 'must return bool'),
    'membership-callable-field': ('main=()=>1 in? [contains=(value:int64)=>true]', 'not a callable field'),
    'membership-float-range': ('main=()=>1.5 in? [0..2]', 'int'),
    'syntax-unclosed-block': ('main=()=>{42', "expected '}'"),
    'syntax-mismatched-block': ('main=()=>[42}', 'expected an expression'),
    'syntax-unclosed-string': ('main=()=>"hello', 'unterminated string'),
    'syntax-empty-interpolation': ('main=()=>"{}"', 'expected an expression'),
    'syntax-missing-member': ('main=()=>value.', 'expected a member name'),
    'generic-duplicate': ('f=<T T>(x:T)=>x\nmain=()=>f(42)', 'duplicate type parameter'),
    'generic-constraint': ('f=<T of int64>(x:T)=>x\nmain=()=>f(42)', 'constrained type parameters'),
    'generic-empty': ('f=<>(x)=>x\nmain=()=>f(42)', 'empty type parameter'),
    'generic-main': ('main=<T>()=>42', 'generic entry point'),
    'generic-local': ('main=()=>{let f=<T>(x:T)=>x return f(42)}', 'generic closure'),
    'generic-type-arity': ('main=()=>{let pool:Pool<int64 string>=[] return 42}', 'expects 1 type argument'),
    'generic-value-type-argument': ('main=()=>{let pool:Pool<42>=[] return 42}', 'type expression'),
    'generic-type-mismatch': ('identity=<T>(x:T):>T=>x\nmain=()=>identity<int64>("bad")', "argument 'x' expects"),
    'syntax-missing-exponent': ('main=()=>1e+', 'expected exponent digits'),
    'syntax-deep-expression': ('main=()=>'+ '(' * 300 + '42' + ')' * 300, 'nested too deeply'),
    'syntax-deep-interpolation': ('main=()=>'+ '"{' * 300 + '42' + '}"' * 300, 'nested too deeply'),
}


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('integer, storage', [('int64', 'local'), ('int64', 'array'),
                                               ('int64', 'fixed'), ('int8', 'array'),
                                               ('uint8', 'array'), ('uint32', 'array'),
                                               ('uint8', 'local')])
def test_core_integer_interval_comparisons(compiler, tmp_path, target, release, integer, storage):
    bits = int(re.search(r'\d+', integer)[0])
    minimum = 0 if integer.startswith('u') else -(2**(bits-1))
    maximum = 2**bits-1 if integer.startswith('u') else 2**(bits-1)-1
    bounds = [(minimum, maximum), (minimum, minimum), (maximum, maximum),
              (-10, 10), (0, 256), (48, 57), (-5, -1), (5, 5), (5, -5),
              (-1, 0), (minimum, 0), (0, maximum), (minimum + 1, maximum - 1),
              (maximum, minimum)]
    bounds = [(lo, hi) for lo, hi in bounds if minimum <= lo <= maximum and minimum <= hi <= maximum]
    rng = random.Random(731)
    values = [minimum, minimum + 1, maximum - 1, maximum, *range(-12, 13),
              47, 48, 49, 56, 57, 58, 255, 256, 257,
              *(rng.randint(minimum, maximum) for _ in range(12))]
    values = [v for v in values if minimum <= v <= maximum]
    read = 'x' if storage == 'local' else 'xs[index]'
    parameter = f'x:{integer}' if storage == 'local' else f'xs:array<{integer}{" length=1" if storage == "fixed" else ""}> index:int64'
    argument = 'x' if storage == 'local' else '[x] 0'
    functions, body, expected = [], [], []
    for low, high in bounds:
        for lower_closed, upper_closed in [(True, True), (False, False),
                                           (True, False), (False, True)]:
            number = len(functions)
            lower = f'x {">=?" if lower_closed else ">?"} ({low})'
            upper = f'x {"<=?" if upper_closed else "<?"} ({high})'
            below = f'x {"<?" if lower_closed else "<=?"} ({low})'
            above = f'x {">?" if upper_closed else ">=?"} ({high})'
            # Reverse operands and conjunction order to cover equivalent source forms.
            if number % 2:
                lower = f'({low}) {"<=?" if lower_closed else "<?"} x'
                upper = f'({high}) {">=?" if upper_closed else ">?"} x'
                below = f'({low}) {">?" if lower_closed else ">=?"} x'
                above = f'({high}) {"<?" if upper_closed else "<=?"} x'
            inside = f'{lower} and {upper}' if number % 3 else f'{upper} and {lower}'
            outside = f'{below} or {above}' if number % 3 else f'{above} or {below}'
            inside, outside = inside.replace('x', read), outside.replace('x', read)
            functions.append(f'''probe_{number}=({parameter}):>int64=>{{
let a={inside} let b={outside} let result:int64=0
if a result+=1
if b result+=2
if {inside} result+=4
if {outside} result+=8
if not ({inside}) result+=16
if not ({outside}) result+=32
return result
}}''')
            body.append(f'printl(to_json([loop x in values probe_{number}({argument})]))')
            expected.append([37 if (x >= low if lower_closed else x > low)
                             and (x <= high if upper_closed else x < high) else 26
                             for x in values])
    literal = ' '.join(f'({x})' for x in values)
    program = '\n'.join(functions) + f'\nmain=()=>{{let values:array<{integer}>=[{literal}]\n'
    program += '\n'.join(body) + '\nreturn 42\n}'
    command, error = build_case_batch(compiler, tmp_path, {'intervals': program},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    assert [json.loads(line) for line in ran.stdout.splitlines()] == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('ordering', ['key', 'comparison'])
def test_core_sort_order(compiler, tmp_path, target, release, ordering):
    (tmp_path / 'keys.jo').write_text('''key = (i: int) -> (int, int): (i % 7, -i)
less = (a: int, b: int) -> bool: key(a) < key(b)
more = (a: int, b: int) -> bool: key(b) < key(a)
''')
    statements = ['from p"keys.jo" import key, less, more', 'main=()=>{']
    expected = []
    for size in [0, 1, 2, 15, 16, 17, 31, 32, 33, 129]:
        values = [(i * 79) % 137 for i in range(size)]
        literal = ' '.join(map(str, values))
        statements += [f'let values_{size}:array<int64>=[{literal}]']
        if ordering == 'key':
            statements += [f'printl(to_json(values_{size}.sorted_by(key)))',
                           f'printl(to_json(values_{size}.sorted_by(key true)))']
        else:
            statements += [f'let ascending_{size}=values_{size}',
                           f'let descending_{size}=values_{size}',
                           f'ascending_{size}.sort_with(less)',
                           f'descending_{size}.sort_with(more)',
                           f'printl(to_json(ascending_{size}))',
                           f'printl(to_json(descending_{size}))']
        statements += [f'printl(to_json(values_{size}))']
        expected += [sorted(values, key=lambda i: (i % 7, -i)),
                     sorted(values, key=lambda i: (i % 7, -i), reverse=True), values]
    statements += ['return 42', '}']
    command, error = build_case_batch(compiler, tmp_path, {'order': '\n'.join(statements)},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    assert [json.loads(line) for line in ran.stdout.splitlines()] == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_json_aggregates(compiler, tmp_path, target, release):
    # Core providers expose aggregate types whose Dewy declaration syntax is
    # still developing. Serialization must use their actual storage and tags.
    (tmp_path / 'types.jo').write_text('''enum Choice: idle, number(value: u64), text(value: str), list(values: int[])
struct Aggregate:
    pair: (u64, str)
    fixed: u64[3]
    nested: str[2][2]
    point: vec3
    mode: Choice
    choice: int | str
make = () -> Aggregate:
    fixed: u64[3] = [1, 2, u64(18446744073709551615)]
    nested: str[2][2] = [["a", "b"], ["c", "d"]]
    Aggregate((u64(18446744073709551615), "tuple"), fixed, nested, vec3(1.0, 2.0, 3.0), Choice.number(u64(18446744073709551615)), "union")
matrix = () -> mat4: mat4()
''')
    program = '''from p"types.jo" import make, Choice, Aggregate, matrix
main=()=>{
    let original=make()
    let text=to_json(original 2)
    printl(text)
    let copy=from_json<Aggregate>(text)
    if copy is? TextError {printl(copy.message) return 1}
    if to_json(copy) not=? to_json(original) return 2
    let variants=[Choice.idle Choice.number(uint64.max) Choice.text("hello") Choice.list([1 2 3])]
    loop variant in variants {
        printl(to_json(variant))
        let loaded=from_json<Choice>(to_json(variant))
        if loaded is? TextError {printl(loaded.message) return 3}
        if loaded not=? variant return 4
        let text_loaded=from_text<Choice>(to_text(variant))
        if text_loaded is? TextError return 5
        if text_loaded not=? variant return 6
    }
    printl(to_json(matrix()))
    printl(to_json(json_value(Choice.text("hello"))))
    let bad=[r'{"missing":[1]}' r'{"number":[]}' r'{"number":[1],"text":["extra"]}' r'{"idle":}']
    loop input in bad {
        let result=from_json<Choice>(input)
        if not (result is? TextError) return 7
    }
    return 42
}
'''
    command, error = build_case_batch(compiler, tmp_path, {'aggregates': program},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    decoder = json.JSONDecoder()
    output = ran.stdout.strip()
    values = []
    while output:
        value, end = decoder.raw_decode(output)
        values.append(value)
        output = output[end:].lstrip()
    maximum = 2**64 - 1
    assert values == [
        {'pair': [maximum, 'tuple'], 'fixed': [1, 2, maximum],
         'nested': [['a', 'b'], ['c', 'd']], 'point': [1, 2, 3],
         'mode': {'number': [maximum]}, 'choice': 'union'},
        'idle', {'number': [maximum]}, {'text': ['hello']}, {'list': [[1, 2, 3]]},
        [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], {'text': ['hello']},
    ]


@pytest.fixture(scope='module')
def compiler():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER to the experimental source-level core')
    return Path(value).resolve(strict=True)


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('unused', [False, True], ids=['generated-only', 'user-binding'])
def test_core_generated_binding_warnings(compiler, tmp_path, release, unused):
    source = tmp_path / 'warnings.dewy'
    binding = 'let forgotten=23' if unused else ''
    source.write_text('Point:type=[x:int64 y:int64]\nmain=()=>{\n'
                      'let base=Point[1 2]\nlet result=[base... x=20 x=40 y=2]\n'
                      + binding + '\nreturn result.x+result.y}\n')
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'program', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    warnings = [line for line in built.stderr.splitlines() if 'warning:' in line]
    assert len(warnings) == int(unused), built.stderr
    if unused:
        assert "'forgotten' is given a value here but never used" in warnings[0]


@pytest.mark.parametrize('mode', [None, 'invalid'])
def test_core_frontend_selection(compiler, tmp_path, mode):
    source = tmp_path / 'main.dewy'
    source.write_text('main=()=>42')
    env = dict(os.environ)
    env.pop('DEWY_CORE_FRONTEND', None)
    env['DEWY_CORE_PARSER'] = str(tmp_path / 'nonexistent-legacy-parser')
    if mode is not None:
        env['DEWY_CORE_FRONTEND'] = mode
    checked = subprocess.run([compiler, 'check', source], env=env, capture_output=True,
                             text=True, timeout=10, check=False)
    if mode is None:
        assert checked.returncode == 0, checked.stdout + checked.stderr
    else:
        assert checked.returncode == 1 and 'DEWY_CORE_FRONTEND' in checked.stderr, checked.stderr


def test_core_debug_local_values(compiler, tmp_path):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or not shutil.which('gdb'):
        pytest.skip('native Linux x86-64 with GDB required')
    source = tmp_path / 'main.dewy'
    source.write_text('''Pair:type=[left:int64 right:int64]
probe=():>int64=>{
let result=Pair[20 21]
result.right+=1
let total=result.left+result.right
printl"{total}"
return total
}
main=()=>probe()
''')
    binary = tmp_path / 'program'
    built = subprocess.run([compiler, 'build', source, '-g', '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    debugged = subprocess.run([
        'gdb', '--batch', '-nx', '-ex', f'break {source}:6', '-ex', 'run',
        '-ex', 'printf "scalar=%ld\\n", total',
        '-ex', 'printf "field=%ld\\n", result.right', str(binary),
    ], capture_output=True, text=True, timeout=30, check=False)
    assert debugged.returncode == 0, debugged.stdout + debugged.stderr
    assert 'scalar=42' in debugged.stdout, debugged.stdout
    assert 'field=22' in debugged.stdout, debugged.stdout


def build_case_batch(compiler, directory, cases, body, release, target, *, arguments=False):
    """Build independent source modules with a caller-supplied test entry point."""
    imports = []
    for i, (name, source) in enumerate(cases.items()):
        (directory / f'{name}.dewy').write_text(source)
        imports.append(f'from p"{name}.dewy" import (main as case_{i})')
    source = directory / 'batch.dewy'
    parameters = 'argv:array<string>' if arguments else ''
    source.write_text('\n'.join(imports) + f'\nmain=({parameters}):>void=>{{\n'
                      + '\n'.join(body) + '\n}\n')
    binary = directory / 'batch'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    if built.returncode:
        message = f'Batch build failed; sources in {directory}\n{built.stdout}{built.stderr}'
        return None, message
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed to execute the generated web runner')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = directory / 'batch.cjs'
        prefix = 'const sloppyArgs = process.argv.slice(1);\n' if arguments else ''
        runner.write_text(prefix + '\n'.join(scripts.parts))
        command = [node, runner]
    return command, None


def isolate_value_batch_failure(compiler, directory, cases, release, target, failure):
    """Split only failed batches; retain failures that require a combined program."""
    names = list(cases)
    original = {name: (None, failure) for name in names}
    if len(names) <= 1:
        return original
    middle = len(names) // 2
    outcomes = {}
    for index, subset in enumerate((names[:middle], names[middle:])):
        part = directory / f'part-{index}'
        part.mkdir()
        outcomes.update(run_value_batch(compiler, part, {name: cases[name] for name in subset},
                                        release, target))
    # An optimizer or module-interaction bug may disappear when split. A
    # failing combined program must never become a passing validation gate.
    if all(code is not None for code, _ in outcomes.values()):
        return original
    return outcomes


def run_value_batch(compiler, directory, cases, release, target):
    """Keep source modules independent while amortizing compiler/runtime startup."""
    names = list(cases)
    body = []
    for i, name in enumerate(names):
        body.extend([f'printl"__DEWY_CASE_BEGIN__:{name}"',
                     f'let result_{i}=case_{i}()',
                     f'printl"__DEWY_CASE_END__:{name}:{{result_{i}}}"'])
    command, failure = build_case_batch(compiler, directory, cases, body, release, target)
    if failure:
        return isolate_value_batch_failure(compiler, directory, cases, release, target, failure)
    if target == 'native':
        command = [*command, 'extra']
    ran = subprocess.run(command, capture_output=True, timeout=10, check=False)
    # Decode without text-mode newline translation: string tests also verify
    # carriage returns and other control characters in the program's output.
    stdout = ran.stdout.decode('utf-8', errors='replace')
    stderr = ran.stderr.decode('utf-8', errors='replace')
    if ran.returncode:
        message = f'Batch exited {ran.returncode}; sources in {directory}\n{stdout}{stderr}'
        return isolate_value_batch_failure(compiler, directory, cases, release, target, message)
    outcomes = {}
    active, output = None, []
    for line in stdout.splitlines(keepends=True):
        if line.startswith('__DEWY_CASE_BEGIN__:'):
            active = line.strip().removeprefix('__DEWY_CASE_BEGIN__:')
            output = []
        elif line.startswith('__DEWY_CASE_END__:'):
            name, code = line.strip().removeprefix('__DEWY_CASE_END__:').rsplit(':', 1)
            if name == active:
                outcomes[name] = (code, ''.join(output))
            active = None
        elif active is not None:
            output.append(line)
    for name in names:
        if name not in outcomes:
            message = f'Missing result for {name}; sources in {directory}\n{stdout}{stderr}'
            return isolate_value_batch_failure(compiler, directory, cases, release, target, message)
    return outcomes


def build_exit_batch(compiler, directory, cases, release, target):
    # One selected case per fresh process: a panic must not prevent the other
    # cases from executing, and a normal return must remain a normal return.
    body = ['if argv.length not=? 2 panic("missing test selector")']
    body.extend(f'if argv[1] =? "{i}" {{case_{i}() return}}' for i in range(len(cases)))
    body.append('panic("invalid test selector")')
    return build_case_batch(compiler, directory, cases, body, release, target, arguments=True)


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_exit_batch_results(compiler, tmp_path, target):
    cases = {'first': 'main=()=>panic("first case panic")',
             'normal': 'main=()=>printl"normal return"',
             'last': 'main=()=>panic("last case panic")'}
    command, failure = build_exit_batch(compiler, tmp_path, cases, False, target)
    assert failure is None, failure
    for index, message in enumerate(['first case panic', 'normal return', 'last case panic']):
        ran = subprocess.run([*command, str(index)], capture_output=True, text=True,
                             timeout=10, check=False)
        assert (ran.returncode == 0) == (index == 1), ran.stdout + ran.stderr
        assert message in ran.stdout + ran.stderr


@pytest.fixture(scope='module')
def error_batches(compiler, tmp_path_factory, request):
    selected, sources = {}, {}
    for item in request.session.items:
        if item.module is not request.module:
            continue
        family = {'test_core_bigint_errors': 'bigint',
                  'test_core_rational_errors': 'rational',
                  'test_core_stepped_range_errors': 'range',
                  'test_core_unit_range_errors': 'range',
                  'test_core_range_index_errors': 'range',
                  'test_core_unpack_errors': 'unpack',
                  'test_core_unpack_single_errors': 'unpack',
                  'test_core_fixed_array_errors': 'bounds',
                  'test_core_extend_slice_errors': 'bounds',
                  'test_core_numeric_array_errors': 'bounds',
                  'test_core_mutable_loop_errors': 'bounds',
                  'test_core_web_array_size_errors': 'bounds',
                  'test_core_set_errors': 'set',
                  'test_core_format_errors': 'format',
                  'test_core_combined_range_errors': 'range',
                  'test_core_compound_errors': 'compound',
                  'test_core_optimizer_bounds': 'bounds'}.get(item.originalname)
        if family is None:
            continue
        params = item.callspec.params
        expression = params['body'] if family in ('range', 'bounds', 'compound', 'unpack', 'set', 'format') else params['expression']
        case = family, expression
        if family in ('range', 'bounds', 'compound', 'unpack', 'set', 'format'):
            sources[case] = f'main=():>void=>{{{expression}}}'
        else:
            sources[case] = f'from {family} import {family}\nmain=():>void=>{{printl"{{{expression}}}"}}'
        selected.setdefault((params['target'], params['release']), []).append(case)
    groups = {}
    for (target, release), cases in selected.items():
        for start in range(0, len(cases), 16):
            group = tuple(cases[start:start + 16])
            for case in group:
                groups[target, release, case] = group
    cached = {}

    def result(family, expression, release, target):
        case = family, expression
        group = groups[target, release, case]
        key = target, release, group
        if key not in cached:
            directory = tmp_path_factory.mktemp(f'errors-{target}-{"release" if release else "debug"}')
            programs = {f'case_{i}': sources[item] for i, item in enumerate(group)}
            cached[key] = build_exit_batch(compiler, directory, programs, release, target)
        command, failure = cached[key]
        if failure:
            pytest.fail(failure)
        return subprocess.run([*command, str(group.index(case))], capture_output=True,
                              text=True, timeout=10, check=False)

    return result


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_value_batch_results(compiler, tmp_path, target, monkeypatch):
    calls = []
    original = build_case_batch

    def counted(*args, **kwargs):
        calls.append(tuple(args[2]))
        return original(*args, **kwargs)

    monkeypatch.setattr(f'{__name__}.build_case_batch', counted)
    cases = {
        'first': 'value=1\nmain=()=>{value+=1 printl"first 🙂" return 42}',
        'wrong': 'value=40\nmain=()=>{printl"wrong result" return 17}',
        'last': 'value=40\nmain=()=>if value =? 40 42 else 1',
    }
    outcomes = run_value_batch(compiler, tmp_path, cases, False, target)
    assert outcomes == {'first': ('42', 'first 🙂\n'), 'wrong': ('17', 'wrong result\n'),
                        'last': ('42', '')}
    assert calls == [('first', 'wrong', 'last')], 'successful batches should compile once'


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('failure', ['compile', 'runtime', 'exit-zero'])
def test_core_value_batch_failures(compiler, tmp_path, target, failure):
    bad = {'compile': 'main=()=>missing_batch_name',
           'runtime': 'main=()=>{panic("intentional batch stop") return 42}',
           'exit-zero': 'main=()=>{exit(0) return 42}'}[failure]
    outcomes = run_value_batch(compiler, tmp_path,
                               {'first': 'main=()=>42', 'bad': bad, 'last': 'main=()=>42'}, False, target)
    assert outcomes['first'] == outcomes['last'] == ('42', '')
    code, diagnostic = outcomes['bad']
    assert code is None and str(tmp_path) in diagnostic
    assert {'compile': 'bad.dewy', 'runtime': 'intentional batch stop',
            'exit-zero': 'Missing result for bad'}[failure] in diagnostic


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_value_batch_combined_failure(compiler, tmp_path, target, monkeypatch):
    original = build_case_batch

    def combined_only(*args, **kwargs):
        if len(args[2]) > 1:
            return None, 'injected failure requiring the combined program'
        return original(*args, **kwargs)

    monkeypatch.setattr(f'{__name__}.build_case_batch', combined_only)
    outcomes = run_value_batch(compiler, tmp_path,
                               {'first': 'main=()=>42', 'last': 'main=()=>42'}, False, target)
    assert outcomes == {name: (None, 'injected failure requiring the combined program')
                        for name in ('first', 'last')}


@pytest.fixture(scope='module')
def value_batches(compiler, tmp_path_factory, request):
    # Collection has already applied -k / node selection. Compile only selected
    # cases in bounded groups and cache each group for its individual IDs.
    selected = {}
    sources = {}
    for item in request.session.items:
        if item.module is not request.module:
            continue
        target = {'test_core_values': 'native', 'test_core_value_web': 'wasm'}.get(item.originalname)
        family = 'values'
        if item.originalname in ('test_core_membership', 'test_core_string_literals'):
            params = item.callspec.params
            if item.originalname == 'test_core_membership':
                family = 'membership'
                source = params['program'] + '\nmain=()=>probe()'
            else:
                # This case additionally checks compiler warnings, which are
                # deliberately verified in its own compilation.
                if params['name'] == 'constant-interpolation':
                    continue
                family = 'strings'
                source = f'main=()=>{{printl({params["expression"]}) return 42}}'
            target = params['target']
        if target is not None:
            params = item.callspec.params
            name = f'{family}-{params["name"]}'
            sources[name] = CASES[params['name']] if family == 'values' else source
            selected.setdefault((target, params['release']), []).append(name)
    groups = {}
    for (target, release), names in selected.items():
        for start in range(0, len(names), VALUE_BATCH_SIZE):
            group = tuple(names[start:start + VALUE_BATCH_SIZE])
            for name in group:
                groups[target, release, name] = group
    cached = {}

    def result(name, release, target, family='values'):
        name = f'{family}-{name}'
        group = groups[target, release, name]
        key = target, release, group
        if key not in cached:
            directory = tmp_path_factory.mktemp(f'values-{target}-{"release" if release else "debug"}')
            cached[key] = run_value_batch(compiler, directory, {n: sources[n] for n in group}, release, target)
        return cached[key][name]

    return result


@pytest.mark.parametrize('name', quick_parameters(CASES, QUICK_CASES))
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_values(value_batches, name, release):
    code, output = value_batches(name, release, 'native')
    assert code == '42', f'{name}: {code}\n{output}'
    if name == 'unicode':
        assert output == 'é🙂 42\n'


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
@pytest.mark.parametrize('both', [False, True], ids=['fallback', 'preferred'])
def test_core_named_module_languages(compiler, tmp_path, extension, both):
    other = 'jo' if extension == 'dewy' else 'dewy'
    (tmp_path / f'helper.{other}').write_text('answer=()=>41' if other == 'dewy' else 'answer = (): 41')
    expected = 41
    if both:
        expected = 42
        (tmp_path / f'helper.{extension}').write_text('answer=()=>42' if extension == 'dewy' else 'answer = (): 42')
    source = tmp_path / f'main.{extension}'
    if extension == 'dewy':
        source.write_text(f'from helper import answer\nmain=()=>if answer() =? {expected} 42 else 1')
    else:
        source.write_text(f'from helper import answer\nmain = (): if answer() == {expected}: 42 else: 1')
    binary = tmp_path / 'imports'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
def test_core_bundled_module_path(compiler, tmp_path, extension):
    (tmp_path / 'bigint.dewy').write_text('bigint=(value)=>0')
    (tmp_path / 'bigint.jo').write_text('bigint = (value): 0')
    source = tmp_path / f'main.{extension}'
    if extension == 'dewy':
        source.write_text('from p"@lib/bigint.dewy" import bigint\nmain=()=>if bigint(42).to_int64() =? 42 42 else 1')
    else:
        source.write_text('from "@lib/bigint.dewy" import bigint\nmain = (): if bigint(42).to_int64() == 42: 42 else: 1')
    binary = tmp_path / 'bundled'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('expression, diagnostic', [
    ('bigint(42)//bigint(0)', 'big integer division by zero'),
    ('bigint(42)%0', 'big integer division by zero'),
    ('bigint(2).pow(-1)', 'big integer exponent must be nonnegative'),
    ('bigint(2)^(-1)', 'big integer exponent must be nonnegative'),
    ('bigint(2)<<(-1)', 'big integer shift count must be nonnegative'),
    ('bigint(-2)>>(-1)', 'big integer shift count must be nonnegative'),
    ('2^(-1)', 'negative integer exponent: use a rational or floating base'),
    ('(2 as uint64)^(-1)', 'negative integer exponent: use a rational or floating base'),
    ('bigint("12x")', 'invalid decimal integer'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_errors(error_batches, expression, diagnostic, target, release):
    ran = error_batches('bigint', expression, release, target)
    assert ran.returncode != 0
    assert diagnostic in ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('notation', ['constructor', 'division'])
def test_core_rational_arithmetic(compiler, tmp_path, target, release, notation):
    values = [(0, 1), (0, -13), (1, 1), (-1, 1), (1, 2), (-1, 2), (2, -3),
              (-2, -3), (4, 6), (10**50, 10**25), (2**127-1, 2**96+1), (-2**63, 2**64-1)]
    pairs = [(a, b) for a in values for b in values if b[0]]
    rng = random.Random(42027)
    for _ in range(96):
        parts = [rng.getrandbits(rng.choice([32, 64, 128, 256])) * rng.choice([-1, 1]) or 1
                 for _ in range(4)]
        pairs.append((tuple(parts[:2]), tuple(parts[2:])))
    (tmp_path / 'cases.txt').write_text('\n'.join(f'{a} {b} {c} {d}' for (a, b), (c, d) in pairs))
    source = tmp_path / 'fractions.dewy'
    body = '''from rational import rational
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\n") {
    let fields=line.split(" ")
    let a=rational(fields[0] fields[1]) let b=rational(fields[2] fields[3])
    let parts=a.divmod(b)
    if a//b not=? parts.quotient or a%b not=? parts.remainder panic("division operators disagree")
    if b*parts.quotient+parts.remainder not=? a panic("division reconstruction")
    printl"{a+b}|{a-b}|{a*b}|{a/b}|{parts.quotient}|{parts.remainder}|{a <? b}|{a =? b}|{a.floor()}|{a.ceil()}|{a.pow(3)}"
}
}
'''
    if notation == 'division':
        body = body.replace('from rational import rational', 'from bigint import bigint')
        body = body.replace('rational(fields[0] fields[1])', 'bigint(fields[0])/bigint(fields[1])')
        body = body.replace('rational(fields[2] fields[3])', 'bigint(fields[2])/bigint(fields[3])')
    source.write_text(body)
    expected = []
    for left, right in pairs:
        a, b = Fraction(*left), Fraction(*right)
        expected.append('|'.join(map(str, [a+b, a-b, a*b, a/b, a//b, a%b]))
                        + f'|{str(a < b).lower()}|{str(a == b).lower()}'
                        + f'|{math.floor(a)}|{math.ceil(a)}|{a**3}')
    binary = tmp_path / 'fractions'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web rational checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'fractions.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_exact_float_conversions(compiler, tmp_path, target, release):
    values = {Fraction(0), Fraction(1, 3), Fraction(2, 3), Fraction(2**4096+1, 2**4096-1)}
    for fraction_bits, bias in [(23, 127), (52, 1023)]:
        minimum = 1-bias-fraction_bits
        exponents = [minimum-1, minimum, minimum+1, -bias, 1-bias, 2-bias,
                     -fraction_bits-1, -1, 0, 1, fraction_bits, fraction_bits+1, bias-1, bias, bias+1]
        for exponent in exponents:
            base = Fraction(2)**exponent
            unit = Fraction(2)**max(exponent-fraction_bits, minimum)
            half = base+unit/2
            values.update([base, base+unit, half, half-unit/2**200,
                           half+unit/2**200, base+3*unit/2])
        largest = (2-Fraction(2)**(-fraction_bits))*Fraction(2)**bias
        half = largest+Fraction(2)**(bias-fraction_bits-1)
        values.update([largest, half, half-Fraction(2)**(bias-fraction_bits-200),
                       half+Fraction(2)**(bias-fraction_bits-200)])
        # These perturbations disappear if the conversion rounds to float64
        # before float32, or rounds either part before dividing.
        half = 1+Fraction(2)**(-fraction_bits-1)
        values.update([half-Fraction(2)**-2000, half+Fraction(2)**-2000])
    rng = random.Random(42029)
    for _ in range(96):
        numerator = rng.getrandbits(rng.choice([32, 64, 256, 1024, 2048, 4096])) or 1
        denominator = rng.getrandbits(rng.choice([32, 64, 256, 1024, 2048, 4096])) or 1
        values.add(Fraction(numerator, denominator))
    values |= {-value for value in values}
    values = sorted(values)
    (tmp_path / 'cases.txt').write_text('\n'.join(f'{v.numerator} {v.denominator}' for v in values))
    # CPython converts Fraction directly to a correctly rounded double. libc's
    # decimal-to-float parser supplies an independent single-precision oracle;
    # 5,000 digits resolve these <=4,096-bit inputs around every rounding tie.
    libc = ctypes.CDLL(None)
    libc.strtof.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    libc.strtof.restype = ctypes.c_float

    def bits(value):
        try:
            double = float(value)
        except OverflowError:
            double = -math.inf if value < 0 else math.inf
        with localcontext() as context:
            context.prec = 5000
            text = str(Decimal(value.numerator)/Decimal(value.denominator))
        single = libc.strtof(text.encode(), None)
        return [struct.unpack('>Q', struct.pack('>d', double))[0],
                struct.unpack('>I', struct.pack('>f', single))[0]]

    expected = ['|'.join(map(str, bits(Fraction(v.numerator))+bits(v))) for v in values]
    source = tmp_path / 'conversions.dewy'
    source.write_text('''from bigint import bigint
from rational import rational
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\n") {
    let fields=line.split(" ")
    let numerator=bigint(fields[0])
    let value=rational(numerator bigint(fields[1]))
    printl"{f64_bits(numerator.to_float64())}|{f32_bits(numerator.to_float32())}|{f64_bits(value.to_float64())}|{f32_bits(value.to_float32())}"
}
}
''')
    binary = tmp_path / 'conversions'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web floating conversion checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'conversions.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_magnitude_reference(compiler, tmp_path, target, release):
    # Python's independently implemented hypot is the numerical reference.
    smallest = math.ulp(0.0)
    largest = float.fromhex('0x1.fffffffffffffp+1023')
    boundary = largest / math.sqrt(2.0)
    cases = [[], [0.0, -0.0], [3.0, 4.0], [3e200, 4e200], [3e-200, 4e-200],
             [smallest], [smallest, smallest], [largest], [largest, smallest],
             [largest, largest], [math.inf, math.nan], [math.nan, -math.inf],
             [math.nan, 1.0], [-math.inf, 0.0]]
    for direction in [0.0, math.inf]:
        value = boundary
        for _ in range(4):
            cases.append([value, value])
            value = math.nextafter(value, direction)
    rng = random.Random(73021)
    for exponent in [-1074, -1060, -1022, -540, -512, -500, -1, 0, 500, 512, 1000, 1022]:
        for count in [1, 2, 3, 9, 64, 257]:
            cases.append([math.ldexp(rng.uniform(-1.0, 1.0), exponent) for _ in range(count)])
    for _ in range(40):
        cases.append([math.ldexp(rng.uniform(-1.0, 1.0), rng.randrange(-1074, 1023))
                      for _ in range(rng.choice([2, 3, 9, 64]))])

    def bits(value):
        return struct.unpack('>Q', struct.pack('>d', value))[0]

    rows = '\n'.join('[' + ' '.join(str(bits(v)) for v in values) + ']' for values in cases)
    source = tmp_path / 'magnitudes.dewy'
    source.write_text('let rows:array<array<uint64>>=[\n' + rows + '''\n]
main=()=>{
loop words in rows {
let values=[loop word in words f64_from_bits(word)]
let pair=if values.length =? 2 hypot(values[0] values[1]) else 0.0
printl"{f64_bits(norm(values))}|{f64_bits(pair)}"
}
return 0
}
''')
    binary = tmp_path / 'magnitudes'
    flags = (['--release'] if release else []) + (['--target', 'wasm'] if target == 'wasm' else [])
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web magnitude checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'magnitudes.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    outputs = ran.stdout.splitlines()
    assert len(outputs) == len(cases), ran.stdout
    for values, output in zip(cases, outputs, strict=True):
        actual = [struct.unpack('>d', struct.pack('>Q', int(v)))[0] for v in output.split('|')]
        expected = [math.nan if any(math.isnan(v) for v in values) else math.hypot(*values),
                    math.hypot(*values) if len(values) == 2 else 0.0]
        for got, want in zip(actual, expected, strict=True):
            if math.isnan(want):
                assert math.isnan(got), (values, got, want)
            elif not math.isfinite(want) or want == 0.0:
                assert bits(got) == bits(want), (values, got, want)
            else:
                assert math.isfinite(got) and abs(got-want) <= 8*math.ulp(want), (values, got, want)


@pytest.mark.parametrize('expression, diagnostic', [
    ('rational(1 0)', 'rational denominator must be nonzero'),
    ('1/0', 'rational denominator must be nonzero'),
    ('(-1)/0', 'rational denominator must be nonzero'),
    ('123456789012345678901234567890/0', 'rational denominator must be nonzero'),
    ('rational(1)/rational(0)', 'rational division by zero'),
    ('rational(1)//0', 'rational division by zero'),
    ('rational(1)%0', 'rational division by zero'),
    ('rational(0).pow(-1)', 'rational division by zero'),
    ('rational(0)^(-1)', 'rational division by zero'),
    ('rational("1/0")', 'invalid rational text'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_rational_errors(error_batches, expression, diagnostic, target, release):
    ran = error_batches('rational', expression, release, target)
    assert ran.returncode != 0
    assert diagnostic in ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('example', ['exact_integers', 'exact_rationals'])
def test_core_exact_example(compiler, tmp_path, target, release, example):
    source = Path(__file__).resolve().parents[2] / f'examples/sloppy_core/{example}.dewy'
    binary = tmp_path / 'exact'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web bigint checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'exact.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    if example == 'exact_rationals':
        harmonic = sum(Fraction(1, n) for n in range(1, 11))
        chance = 45 * Fraction(1, 6)**2 * Fraction(5, 6)**8
        quotient, remainder = divmod(Fraction(-7, 3), Fraction(2, 5))
        assert ran.stdout.splitlines() == [f'First ten harmonic terms: {harmonic}',
                                          f'Exactly two sixes in ten rolls: {chance}',
                                          'Reciprocal cube of 2/3: 27/8', 'Sixty exact time steps: 1',
                                          f'Floor quotient: {quotient}; remainder: {remainder}']
        return
    quotient, remainder = divmod(-123456789012345678901234567890, 9876543210987654321)
    assert ran.stdout.splitlines() == [f'100! = {math.factorial(100)}',
                                      f'Ways to choose 50 of 100: {math.comb(100, 50)}',
                                      f'Floor quotient: {quotient}; remainder: {remainder}',
                                      'Reconstruction: true', f'2^256 = {2**256}']


def integer_literal(value, prefix, alphabet):
    digits = ''
    while value:
        value, digit = divmod(value, len(alphabet))
        digits = alphabet[digit] + digits
    digits = digits or '0'
    return prefix + '_'.join(digits[i:i+4] for i in range(0, len(digits), 4))


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_literal_bases(compiler, tmp_path, target, release):
    alphabets = [('0b', '01'), ('0t', '012'), ('0q', '0123'), ('0s', '012345'),
                 ('0o', '01234567'), ('0d', '0123456789'), ('0z', '0123456789xe'),
                 ('0x', '0123456789ABCDEF')]
    values = [2**63+1, 2**64, 2**64+1, 2**127-1, 2**128+17, 2**255+43, 2**1023+7]
    rng = random.Random(42028)
    values += [rng.getrandbits(257) for _ in range(8)]
    statements, expected = [], []
    for prefix, alphabet in alphabets:
        for value in values:
            literal = integer_literal(value, prefix, alphabet)
            for sign in ['', '-']:
                statements.append(f'printl"{{{sign}{literal}}}"')
                expected.append(str(-value if sign else value))
    # A local module cannot replace the implementation of a numeric literal.
    (tmp_path / 'bigint.dewy').write_text('BigInt:type=[wrong:bool]\n')
    source = tmp_path / 'literals.dewy'
    source.write_text('main=():>void=>{\n' + '\n'.join(statements) + '\n}\n')
    binary = tmp_path / 'literals'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web literal checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'literals.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_literal_modules(compiler, tmp_path, target, release):
    (tmp_path / 'rational.dewy').write_text('rational=()=>"wrong library"\n')
    (tmp_path / 'constants.dewy').write_text('''const amount=123456789012345678901234567890
const fraction=amount/7
read=(value=amount)=>value+1
fractional=(value=fraction)=>value*7
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''from constants import amount, read, fractional
main=()=>if amount+1 =? read() and read(18446744073709551616) =? 18446744073709551617
and fractional() =? amount 42 else 1
''')
    binary = tmp_path / 'modules'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web literal checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'modules.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_arithmetic(compiler, tmp_path, target, release):
    boundary = [0, 1, -1, 2, -2]
    for bits in [31, 32, 63, 64, 96, 128]:
        boundary.extend([2**bits-1, 2**bits, 2**bits+1, -(2**bits-1), -(2**bits+1)])
    divisors = [1, -1, 3, -3, 2**32-1, -(2**32-1), 2**32+1, -(2**32+1), 2**96-1, -(2**96+1)]
    pairs = [(a, b) for a in boundary for b in divisors]
    # Algorithm D: a low divisor limb forces the final add-back; a quotient
    # estimate at the limb base forces the estimate correction before subtract.
    base = 2**32
    for divisor in [base**2 * (base//2) + 1, base**2 - 1, base**2 + base - 1]:
        for multiplier in [2, base - 1, base, base + 1]:
            for offset in [-1, 0, 1]:
                numerator = divisor * multiplier + offset
                pairs.extend((a, b) for a in [numerator, -numerator] for b in [divisor, -divisor])
    rng = random.Random(42026)
    for _ in range(128):
        a = rng.getrandbits(rng.choice([32, 64, 128, 256, 512]))
        b = rng.getrandbits(rng.choice([32, 64, 128, 256])) or 1
        pairs.append((a * rng.choice([-1, 1]), b * rng.choice([-1, 1])))
    (tmp_path / 'cases.txt').write_text('\n'.join(f'{a} {b}' for a, b in pairs))
    source = tmp_path / 'bigint.dewy'
    source.write_text('''from bigint import BigInt, bigint
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\n") {
    let fields=line.split(" ")
    let a=bigint(fields[0]) let b=bigint(fields[1])
    let parts=a.divmod(b)
    if a//b not=? parts.quotient or a%b not=? parts.remainder panic("division operators disagree")
    printl"{a+b}|{a-b}|{a*b}|{parts.quotient}|{parts.remainder}|{a.gcd(b)}|{a <? b}|{a =? b}"
}
}
''')
    expected = ['|'.join(map(str, [a+b, a-b, a*b, a//b, a%b, math.gcd(a, b)]))
                + f'|{str(a < b).lower()}|{str(a == b).lower()}' for a, b in pairs]
    binary = tmp_path / 'bigint'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web bigint checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'bigint.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('form', ['unit', 'stepped', 'stored-unit', 'stored-stepped',
                                  'stored-open-unit', 'stored-open-stepped'])
def test_core_integer_ranges(compiler, tmp_path, target, release, form):
    cases, expected = [], []

    def add(kind, start, second, end, inclusive):
        if form.startswith('stored-') and kind != 's':
            return
        step = second - start if form.endswith('stepped') else 1
        if not step:
            return
        stop = end + (1 if step > 0 else -1) if inclusive else end
        values = range(start, stop, step)
        if form.startswith('stored-open-'):
            values = values[1:]
        try:
            if len(values) > 32:
                return
        except OverflowError:
            return
        cases.append(f'{kind}|{start}|{second}|{end}|{int(inclusive)}')
        expected.extend(str(value) for value in values)
        if form.startswith('stored-'):
            expected.extend(str(needle in values).lower() for needle in [start, second, end, 0])
        expected.append('end')

    for kind, edges in [('s', [-2**63, -2**63+1, -4, 0, 4, 2**63-2, 2**63-1]),
                        ('u', [0, 1, 2, 2**63-1, 2**63, 2**64-2, 2**64-1])]:
        for start in edges:
            for second in (edges if form.endswith('stepped') else [start]):
                for end in edges:
                    for inclusive in [False, True]:
                        add(kind, start, second, end, inclusive)
    rng = random.Random(42028)
    for _ in range(128):
        start = rng.randrange(-100, 101)
        step = rng.choice([n for n in range(-17, 18) if n])
        add('s', start, start + step, start + rng.randrange(-50, 51), rng.choice([False, True]))
    (tmp_path / 'cases.txt').write_text('\n'.join(cases))
    source = tmp_path / 'ranges.dewy'
    source.write_text('''from bigint import bigint
emit=<T>(a:T b:T end:T inclusive:bool):>void=>{
let count:int64=0
if inclusive {
    loop i in [a,b..end] {if count >=? 32 panic("loop did not terminate") printl(i) count+=1}
} else {
    loop i in [a,b..end) {if count >=? 32 panic("loop did not terminate") printl(i) count+=1}
}
printl"end"
}
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\\n") {
    let fields=line.split("|") let inclusive=fields[4] =? "1"
    if fields[0] =? "s" {
        let a=bigint(fields[1]).to_int64() let b=bigint(fields[2]).to_int64() let end=bigint(fields[3]).to_int64()
        if a is? none or b is? none or end is? none panic("invalid signed bounds")
        emit<int64>(a b end inclusive)
    } else {
        let a=bigint(fields[1]).to_uint64() let b=bigint(fields[2]).to_uint64() let end=bigint(fields[3]).to_uint64()
        if a is? none or b is? none or end is? none panic("invalid unsigned bounds")
        emit<uint64>(a b end inclusive)
    }
}
}
''')
    if form.startswith('stored-'):
        source.write_text(source.read_text()
                          .replace('loop i in [a,b..end] {', 'let r=[a,b..end] loop i in r {')
                          .replace('loop i in [a,b..end) {', 'let r=[a,b..end) loop i in r {')
                          .replace('count+=1}', 'count+=1} printl(a in? r) printl(b in? r) printl(end in? r) printl(0 in? r)')
                          .replace('emit<uint64>(a b end inclusive)', 'panic("stored inputs must be signed")'))
    if form.endswith('unit'):
        source.write_text(source.read_text().replace('a,b..', 'a..'))
    if form.startswith('stored-open-'):
        source.write_text(source.read_text().replace('let r=[', 'let r=('))
    binary = tmp_path / 'ranges'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web range checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'ranges.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('body', [
    f'let start:{kind}={start} let count:int64=0 loop i in [start..] {{printl(i) count+=1 if count >? 3 {{return}} continue}}'
    for kind, start in [('int8', 126), ('uint8', 254), ('int16', 32766), ('uint16', 65534),
    ('int32', 2147483646), ('uint32', 4294967294),
    ('int64', 9223372036854775806), ('uint64', 18446744073709551614)]
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_unit_range_errors(error_batches, body, target, release):
    ran = error_batches('range', body, release, target)
    assert ran.returncode != 0, ran.stdout + ran.stderr
    assert 'range exhausted its integer type' in ran.stdout + ran.stderr
    assert len(ran.stdout.splitlines()) == 2


@pytest.mark.parametrize('body', [
    f'let start:{kind}={start} let count:int64=0 loop i in [start..] {join} j in [0..4) {{printl(i) count+=1 if count >? 3 {{return}}}}'
    for join in ['and', 'or']
    for kind, start in [('int8', 126), ('uint8', 254),
                        ('int64', 9223372036854775806), ('uint64', 18446744073709551614)]
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_combined_range_errors(error_batches, body, target, release):
    ran = error_batches('range', body, release, target)
    assert ran.returncode != 0, ran.stdout + ran.stderr
    assert 'range exhausted its integer type' in ran.stdout + ran.stderr
    assert len(ran.stdout.splitlines()) == 2


@pytest.mark.parametrize('body, diagnostic', [
    ('loop i in [2,2..] and x in [1 2] {printl(i+x)}', 'range step must be nonzero'),
    ('loop i in [int64.max-1,int64.max..] and x in [1 2 3] {printl(i)}', 'range exhausted its integer type'),
    ('loop i in [int64.min+1,int64.min..] or x in [1 2 3] {printl(i)}', 'range exhausted its integer type'),
    ('let r=[2,2..10] printl(3 in? r)', 'range step must be nonzero'),
    ('printl(3 in? [2,2..10])', 'range step must be nonzero'),
    ('loop i in [2,2..10] {printl(i)}', 'range step must be nonzero'),
    ('let start:int64=9223372036854775806 let second:int64=9223372036854775807\nloop i in [start,second..] {printl(i)}', 'range exhausted its integer type'),
    ('let start:uint64=18446744073709551614 let second:uint64=18446744073709551615\nloop i in [start,second..] {printl(i)}', 'range exhausted its integer type'),
    ('let start:uint8=254 let second:uint8=255\nloop i in [start,second..] {printl(i)}', 'range exhausted its integer type'),
    ('let start:int8=-127 let second:int8=-128\nloop i in [start,second..] {printl(i)}', 'range exhausted its integer type'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_stepped_range_errors(error_batches, body, diagnostic, target, release):
    ran = error_batches('range', body, release, target)
    assert ran.returncode != 0
    assert diagnostic in ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_bits(compiler, tmp_path, target, release):
    rng = random.Random(42027)
    values = [0, 1, -1]
    for bits in [31, 32, 33, 63, 64, 65, 127, 128, 256]:
        for delta in [-1, 0, 1]:
            value = 2**bits + delta
            values.extend([value, -value])
    counts = [0, 1, 31, 32, 33, 63, 64, 65, 127, 256, 4096]
    cases = [(a, b, counts[i % len(counts)]) for i, a in enumerate(values)
             for b in [0, 1, -1, 2**32-1, -(2**32+1), 2**128]]
    for _ in range(128):
        a = rng.getrandbits(rng.choice([32, 64, 256, 512, 1024, 4096])) * rng.choice([-1, 1])
        b = rng.getrandbits(rng.choice([32, 64, 256, 512, 1024, 4096])) * rng.choice([-1, 1])
        cases.append((a, b, rng.choice(counts)))
    (tmp_path / 'cases.txt').write_text('\n'.join(f'{a} {b} {count}' for a, b, count in cases))
    source = tmp_path / 'bits.dewy'
    source.write_text('''from bigint import bigint
main=():>void=>{
let input=$include_bytes(p"cases.txt") as string|none
if input is? none panic("invalid test data")
loop line in input.split("\\n") {
    let fields=line.split(" ")
    let a=bigint(fields[0]) let b=bigint(fields[1]) let count=to_int(fields[2])
    if count is? none panic("invalid shift count")
    printl"{a and b}|{a or b}|{a xor b}|{not a}|{a << count}|{a >> count}"
}
}
''')
    expected = ['|'.join(map(str, [a & b, a | b, a ^ b, ~a, a << count, a >> count]))
                for a, b, count in cases]
    binary = tmp_path / 'bits'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web bigint checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'bits.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('body', [
    'let xs:array<int64>=[] printl(xs[0] >? 5 and xs[0] <? -5)',
    'let xs:array<int64>=[] printl(xs[0] <=? 5 or xs[0] >=? -5)',

    '''let values=[42] let index:int64=0
if values[index] >? 0 and values[index] <? 100 {index=-1}
printl"{values[index]}"''',
    '''let values=[42]
if values[0] >? 0 and values[0] <? 100 {values.clear()}
printl"{values[0]}"''',
    '''let values:array<int64>=[] let skip=args().length >? 0
if not skip and values[0] >? 0 {printl"unreachable"}
printl"{values[0]}"''',
    '''let values=[42]
loop i in [0..2) {
    if values[0] >? 0 and values[0] <? 100 {values.clear()}
}''',
    'let values=[42] loop i in [0..values.length) {i=values.length printl(values[i])}',
    'let values=[42] loop i in [0..values.length) {i=-1 printl(values[i])}',
    'let values=[42] loop i in [0..values.length) {let change=(@x:int64)=>{x=1} change(@i) printl(values[i])}',
    'let record=[values=[42]] loop i in [0..record.values.length) {i=1 printl(record.values[i])}',
    'let values=[42] loop i in [0..values.length) {printl(values[i]) i=1 printl(values[i])}',
    'let values=[42] loop i in [0..values.length) {loop j in [0..values.length) {j=1 printl(values[j])} printl(values[i])}',
    'let values=[42] loop i in [0..1) {i=-1 loop j in [i..values.length) {printl(values[j])}}',
    'let values=[42] loop i in [0..1) {loop j in [i+9223372036854775807+1..values.length) {printl(values[j])}}',
    'let values=[42] loop i in [0..values.length) {loop j in [0,-1..-2] {printl(values[j])} printl(values[i])}',
    'let values=[42] loop i in [0,2..values.length) {i=1 printl(values[i])}',
    'let values=[42] loop i in [0,2..values.length) {values.clear() printl(values[i])}',
    'let values=[20 22] loop i in [0,2..values.length] {printl(values[i])}',
    'let record=[values=[42]] loop i in [0,2..record.values.length) {i=-1 printl(record.values[i])}',
], ids=['empty-interval-read', 'full-interval-read', 'changed-index', 'changed-length', 'skipped-check', 'next-iteration',
        'counter-end', 'counter-negative', 'counter-reference',
        'counter-record-field', 'counter-after-read', 'counter-nested',
        'counter-nested-start', 'counter-overflowed-start', 'counter-descending',
        'step-counter-end', 'step-resized', 'step-inclusive', 'step-counter-field'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_optimizer_bounds(error_batches, body, target, release):
    ran = error_batches('bounds', body, release, target)
    assert ran.returncode != 0, ran.stdout + ran.stderr
    assert 'out of bounds' in ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_word_power_arithmetic(compiler, tmp_path, target, release):
    signed = [-2**63, -2**63+1, -65537, -3, -2, -1, 0, 1, 2, 3, 65537, 2**63-1]
    unsigned = [0, 1, 2, 3, 2**32-1, 2**32, 2**63, 2**64-2, 2**64-1]
    exponents = [0, 1, 2, 3, 7, 16, 31, 32, 63, 64, 127, 255]
    source = tmp_path / 'powers.dewy'
    source.write_text(f'''main=():>void=>{{
let signed:array<int64>=[{' '.join(map(str, signed))}]
let unsigned:array<uint64>=[{' '.join(map(str, unsigned))}]
let exponents:array<int64>=[{' '.join(map(str, exponents))}]
loop a in signed {{loop n in exponents {{printl"{{a^n}}"}}}}
loop a in unsigned {{loop n in exponents {{printl"{{a^n}}"}}}}
}}
''')
    expected = []
    for a in signed:
        for n in exponents:
            value = pow(a, n, 2**64)
            expected.append(str(value if value < 2**63 else value - 2**64))
    expected.extend(str(pow(a, n, 2**64)) for a in unsigned for n in exponents)
    binary = tmp_path / 'powers'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web power checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'powers.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_set_algebra(compiler, tmp_path, target, release):
    keys = [-2, 0, 3, 5]
    members = [[key for i, key in enumerate(keys) if mask & (1 << i)] for mask in range(16)]
    literals = ' '.join('set['+' '.join(map(str, values))+']' for values in members)
    source = tmp_path / 'sets.dewy'
    source.write_text('''digest=(values:set<int64>):>int64=>{
let result:int64=7 loop value in values {result=result*11+value+5} return result}
main=():>void=>{
let values:array<set<int64>>=['''+literals+''']
loop a in values {loop b in values {
printl(digest(a & b)) printl(digest(a | b))
printl(digest(a-b)) printl(digest(a xor b)) printl(a =? b)
}}
}''')
    expected = []
    for left in members:
        for right in members:
            a, b = set(left), set(right)
            results = ([v for v in left if v in b], list(dict.fromkeys(left+right)),
                       [v for v in left if v not in b],
                       [v for v in left if v not in b]+[v for v in right if v not in a])
            for values in results:
                checksum = 7
                for value in values:
                    checksum = checksum*11+value+5
                expected.append(str(checksum))
            expected.append(str(a == b).lower())
    binary = tmp_path / 'sets'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web set checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'sets.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bounded_remainder_ir(compiler, tmp_path, target, release):
    source = tmp_path / 'bounded.dewy'
    source.write_text(CASES['numeric-bounded-remainder'])
    flags = ['--ir', *(['--release'] if release else []), *(['--target', 'wasm'] if target == 'wasm' else [])]
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'bounded', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    # The recurrence may now live entirely in main after inlining.
    output = built.stdout + built.stderr
    probe = (re.search(r'^fn f_probe_.*?(?=^fn |\Z)', output, re.M | re.S)
             or re.search(r'^fn f_main_.*?(?=^fn |\Z)', output, re.M | re.S))
    assert probe, 'bounded recurrence was not emitted'
    assert re.search(r' = (mulhu|remu) ', probe[0]), 'bounded recurrence still uses signed remainder'
    assert ' = mulhs ' not in probe[0]


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_constant_floor_ir(compiler, tmp_path, target):
    source = tmp_path / 'constant.dewy'
    source.write_text('''probe=(a:int64):>int64=>a%3+a//3+a%8+a//8
main=()=>probe(-7)
''')
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target,
                            '-o', tmp_path / 'constant'],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_probe_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert probe, 'constant arithmetic probe was not emitted'
    assert 'call' not in probe[0], 'literal floor arithmetic still calls a helper in default builds'


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_fast_inline(compiler, tmp_path, target):
    source = tmp_path / 'leaf.jo'
    source.write_text('''counter = 0
next = () -> int:
    counter += 1
    counter
small = (x: int) -> int:
    if x < 0: return -x
    x + 2
@noinline
kept = (x: int) -> int: x * 2
bump = (value: mut int) -> int:
    value += 2
    value
main = () -> int:
    x = 10
    a = small(next())
    b = small(-3)
    c = kept(4)
    d = bump(x)
    if a + b + c + d + x + counter == 39: return 42
    1
''')
    binary = tmp_path / 'leaf'
    built = subprocess.run([compiler, 'build', source, '--ir', '--target', target, '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    main = re.search(r'^fn f_main_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    assert main, 'main was not emitted'
    assert main[0].count(' = call ') == 1, 'only the @noinline call should remain'
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web inlining checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'leaf.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


def test_core_many_record_types(compiler, tmp_path):
    # Record instances bypass the ordinary type interner. Enough of them can
    # outgrow even its next doubled table before it is asked to intern again.
    source = tmp_path / 'records.jo'
    source.write_text(record_source(5000))
    checked = subprocess.run([compiler, 'check', source], capture_output=True,
                             text=True, timeout=10, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_type_instance_inference(compiler, tmp_path, release):
    source = Path(__file__).resolve().parents[2] / 'core/tests/type_instances.jo'
    binary = tmp_path / 'type_instances'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'ok\n'


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_function_reachability(compiler, tmp_path, target):
    source = Path(__file__).resolve().parents[2] / 'core/tests/function_reachability.jo'
    binary = tmp_path / 'reachable'
    built = subprocess.run([compiler, 'build', source, '--target', target,
                            '--release', '--ir', '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    functions = re.findall(r'^fn (\S+)', built.stdout + built.stderr, re.M)
    assert any(name.startswith('f_api_step_') for name in functions), functions
    assert any(name.startswith('f_recursive_sum_') for name in functions), functions
    assert not any(name.startswith(('f_tiny_step_', 'f_obsolete_branch_')) for name in functions), functions
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web reachability checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'reachable.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    assert not ran.stdout


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_dictionary_presence_ir(compiler, tmp_path, target):
    source = tmp_path / 'presence.dewy'
    source.write_text('''probe=(values:dict<int64 array<int64>> key:int64):>bool=>values.get(key) is? none
main=()=>if probe([1->[42]] 1) 1 else 42
''')
    flags = ['--ir', *(['--target', 'wasm'] if target == 'wasm' else [])]
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'presence', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe, 'presence probe was not emitted'
    assert ' = load ' not in probe[0], 'presence query still loads an optional tag'


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_nested_exit_cleanup(compiler, tmp_path, target, release):
    # Keep a separate body for the IR assertion. Dewy execution of the same
    # control flow is covered by optimizer-nested-exits in the value batches.
    source = tmp_path / 'nested_exit.jo'
    source.write_text('''@noinline
reachability_probe = (first: bool, second: bool) -> int:
    if first:
        if second: return 20
        else: return 21
    else: return 22
    print("unreachable tail")
    return 99
main = () -> int: reachability_probe(true, false)
''')
    flags = ['--ir', *(['--release'] if release else [])]
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'nested_exit', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = re.search(r'^fn f_reachability_probe_.*?(?=^fn |\Z)',
                      built.stdout + built.stderr, re.M | re.S)
    assert probe, 'nested-return function was not emitted'
    assert ' = call ' not in probe[0], 'unreachable printing remained after nested returns'


@pytest.mark.parametrize('target', ['native', 'wasm', 'linux-arm64'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_integer_select(compiler, tmp_path, target, release):
    runner = shutil.which('qemu-aarch64' if target == 'linux-arm64' else 'node')
    if target != 'native' and not runner:
        pytest.skip(f'Runner unavailable for {target}')
    values = [-(1 << 63), -(1 << 63)+1, -129, -1, 0, 1, 127, (1 << 63)-1]
    rng = random.Random(42031)
    values += [rng.randrange(-(1 << 63), 1 << 63) for _ in range(128)]
    source = tmp_path / 'select.dewy'
    source.write_text(f"""pick=(x:int64 y:int64 flag:bool):>int64=>
if flag (x xor y)+1 else (x-y)*3
main=():>void=>{{
let values:array<int64>=[{' '.join(map(str, values))}]
loop i in [0..values.length) {{
let x=values[i] let y=values[values.length-1-i]
loop flag in [true false] {{printl(pick(x y flag))}}
}}
}}
""")
    expected = []
    for x, y in zip(values, reversed(values), strict=True):
        for result in [(x ^ y)+1, (x-y)*3]:
            expected.append(str((result+(1 << 63)) % (1 << 64)-(1 << 63)))
    binary = tmp_path / 'select'
    flags = ['--ir', *(['--release'] if release else [])]
    if target != 'native':
        flags += ['--target', target]
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    pick_ir = re.search(r'^fn f_(?:pick|main)_.*?(?=^fn |\Z)', built.stdout + built.stderr, re.M | re.S)
    if release:
        assert pick_ir and ' = select ' in pick_ir[0], 'conditional selection was not emitted'
    command = [binary]
    if target == 'linux-arm64':
        command = [runner, binary]
    elif target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        script = tmp_path / 'select.cjs'
        script.write_text('\n'.join(scripts.parts))
        command = [runner, script]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('host', ['windows', 'macos', 'linux-arm64'])
def test_core_compiler_hosts(compiler, tmp_path, host):
    root = Path(__file__).resolve().parents[2]
    binary = tmp_path / ('compiler.exe' if host == 'windows' else 'compiler')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(DEWY_CORE_LIB=str(compiler.parent.parent / 'lib'), SLOPPY_EMIT_WORKERS='1')
    built = subprocess.run([compiler, 'build', root / 'core/compiler/main.jo', '--target', host,
                            '-o', binary], env=env, capture_output=True, text=True,
                           timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    header = binary.read_bytes()[:20]
    if host == 'windows':
        assert header[:2] == b'MZ'
    elif host == 'macos':
        assert header[:8] == bytes.fromhex('cffaedfe0c000001')
    else:
        assert header[:4] == b'\x7fELF' and int.from_bytes(header[18:20], 'little') == 183
        if runner := shutil.which('qemu-aarch64'):
            source = tmp_path / 'values.dewy'
            source.write_text('''main=()=>{
let original=[20 21] let changed=original
loop @item in changed {item+=1}
assert(original =? [20 21] and changed =? [21 22])
printl"{changed[1]} {1/3+1/6} {18446744073709551616+1}"
return 0
}''')
            for flags in [[], ['--release']]:
                program = tmp_path / 'values'
                built = subprocess.run([runner, binary, 'build', source, '-o', program, *flags],
                                       env=env, capture_output=True, text=True, timeout=30, check=False)
                assert built.returncode == 0, built.stdout + built.stderr
                ran = subprocess.run([runner, program], env=env, capture_output=True, text=True,
                                     timeout=10, check=False)
                assert ran.returncode == 0, ran.stdout + ran.stderr
                assert ran.stdout == '22 1/2 18446744073709551617\n'


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_unsigned_floor_arithmetic(compiler, tmp_path, target, release):
    maximum = (1 << 64) - 1
    numerators = [0, 1, 2, 127, 255, 65535, (1 << 32) - 1, 1 << 32,
                  (1 << 63) - 1, 1 << 63, maximum - 1, maximum]
    denominators = [1, 2, 3, 255, 1000000007, (1 << 32) - 1, 1 << 32, 1 << 63, maximum]
    literal_divisors = [*[1 << shift for shift in range(64)], 3, 5, 7, 31, 255, 1000, 1000000007]
    constants = '\n'.join(f'printl"{{a//{b}}} {{a%{b}}}"' for b in literal_divisors)
    source = tmp_path / 'unsigned.dewy'
    source.write_text(f'''main=():>void=>{{
let values:array<uint64>=[{' '.join(map(str, numerators))}]
let divisors:array<uint64>=[{' '.join(map(str, denominators))}]
loop a in values {{
    loop b in divisors {{
        let quotient:uint64=a//b
        let remainder:uint64=a%b
        printl"{{quotient}} {{remainder}}"
    }}
    {constants}
}}
}}
''')
    expected = [f'{a // b} {a % b}' for a in numerators for b in denominators + literal_divisors]
    binary = tmp_path / 'unsigned'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web unsigned arithmetic checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'unsigned.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_signed_floor_arithmetic(compiler, tmp_path, target, release):
    minimum, maximum = -(1 << 63), (1 << 63) - 1
    numerators = [minimum, minimum + 1, -1000000007, -129, -7, -1, 0, 1, 7, 129, 1000000007, maximum - 1, maximum]
    denominators = [minimum, minimum + 1, -1000000007, -129, -3, -1, 1, 2, 3, 129, 1000000007, maximum]
    powers = [1 << shift for shift in range(63)]
    constants = powers + [-3, 3, 5, 7, 9, 10, 31, 63, 1000, 2147483647,
                          -129, 129, -1000000007, 1000000007, minimum, maximum]
    constant_cases = '\n'.join(f'printl"{{a%{b}}} {{a//{b}}}"' for b in constants)
    source = tmp_path / 'floor.dewy'
    source.write_text(f'''main=():>void=>{{
loop a in [{' '.join(map(str, numerators))}] {{
    loop b in [{' '.join(map(str, denominators))}] {{
        let remainder=a%b
        let quotient=a//b
        printl"{{remainder}} {{quotient}}"
    }}
    {constant_cases}
}}
}}
''')
    expected = [f'{a % b} {minimum if a == minimum and b == -1 else a // b}'
                for a in numerators for b in denominators + constants]
    binary = tmp_path / 'floor'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web arithmetic checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'floor.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_scalar_conditional_results(compiler, tmp_path, target, release):
    source = tmp_path / 'conditional.dewy'
    source.write_text('''let calls:int64=0
pick=(yes:bool x:int8 y:int8):>int8=>if yes {calls+=1 x} else {calls+=10 y}
floating=(yes:bool x:float32 y:float32):>float32=>if yes x else y
early=(x:int64):>int64=>if x <? 0 {return -x} else if x =? 0 7 else {let values=[x 2] values[0]+values[1]}
main=():>void=>{
    let total:int64=0
    loop i in [0..100) {
        let value:int8=pick(i%2 =? 0 (-128) 127)
        total+=value as int64
    }
    let real=floating(true 1.25 8.5)+floating(false 1.25 8.5)
    let wide:uint64=if total <? 0 18446744073709551615 as uint64 else 0 as uint64
    let truth=if calls =? 550 total =? -50 else false
    let jumped:int64=0
    loop i in [0..10) {
        jumped+=if i =? 2 {continue} else if i =? 5 {break} else i
    }
    printl"{total} {calls} {real} {wide} {truth} {jumped} {early(-3)+early(0)+early(30)}"
}
''')
    binary = tmp_path / 'conditional'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web conditional checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'conditional.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.split() == ['-50', '550', '9.75', '18446744073709551615', 'true', '8', '42']


@pytest.mark.parametrize(('name', 'expression', 'expected'), [
    ('format-fixed-even', 'format(1.125 ".2f")', '1.12'),
    ('format-fixed-up', 'format(1.375 ".2f")', '1.38'),
    ('format-negative-zero', 'format(-0.0 ".1f")', '-0.0'),
    ('format-f32-short', 'format(float32(0.1) ">8")', '     0.1'),
    ('format-radix-padding', 'format(255 "#06x")', '0x00ff'),
    ('format-narrow-signed', 'format(int8(-1) "#x")', '-0x1'),
    ('format-narrow-unsigned', 'format(uint8(255) "#06x")', '0x00ff'),
    ('format-u32', 'format(uint32.max "x")', 'ffffffff'),
    ('format-i32', 'format(int32.min "d")', '-2147483648'),
    ('format-i64', 'format(int64.min "d")', '-9223372036854775808'),
    ('format-u64', 'format(uint64.max "d")', '18446744073709551615'),
    ('format-grouping', 'format(uint64.max ",")', '18,446,744,073,709,551,615'),
    ('format-integer-fixed', 'format(42 "08.2f")', '00042.00'),
    ('format-unsigned-fixed', 'format(uint64(42) ".2f")', '42.00'),
    ('format-signed-group', 'format(1234.5 "+,.2f")', '+1,234.50'),
    ('format-percent', 'format(0.125 ".1%")', '12.5%'),
    ('format-exponent', 'format(12500 ".2e")', '1.25e+04'),
    ('format-general', 'format(12345 ".3g")', '1.23e+04'),
    ('format-center', 'format("θ" "^5")', '  θ  '),
    ('format-unicode', 'format("é🙂" ">5")', '   é🙂'),
    ('format-graphemes', 'format("é👩🏽‍💻" ">5")', '   é👩🏽‍💻'),
    ('format-no-truncation', 'format("é👩🏽‍💻" "<1")', 'é👩🏽‍💻'),
    ('format-fill', 'format("ok" "-<5s")', 'ok---'),
    ('format-zero', 'format(0 "b")', '0'),
    ('format-interpolation', '"θ = {format(1.25 ".1f")}°"', 'θ = 1.2°'),
    ('constant-interpolation', '"answer {42}"', 'answer 42'),
    ('unicode', '"\\u0065\\u0301 \\u{1F642} \\U00E9"', 'é 🙂 é'),
    ('unicode-boundaries', '"\\u0000\\u007F\\u0080\\u07FF\\u0800\\uD7FF\\uE000\\u{10FFFF}"', '\x00\x7f\x80߿ࠀ\ud7ff\ue000\U0010ffff'),
    ('raw', 'r"C:\\new\\textures\\{sprite}.png"', 'C:\\new\\textures\\{sprite}.png'),
    ('raw-single', "r'\\u1234 {value}'", '\\u1234 {value}'),
    ('triple', '"""first "quoted"\n  second"""', 'first "quoted"\n  second'),
    ('triple-single', "'''first 'quoted'\n  second'''", "first 'quoted'\n  second"),
    ('raw-triple', 'r"""first \\n {value}\n  second"""', 'first \\n {value}\n  second'),
    ('nested-raw', '"answer {r"{value}".length}"', 'answer 7'),
    ('nested-triple', '"answer {"""hello "there"!""".length}"', 'answer 14'),
    ('interpolation-comment', '"answer { # " } ignored\n 42}"', 'answer 42'),
    ('continued-line', '"first\\\nsecond"', 'firstsecond'),
    ('carriage-return', '"first\\r\\nsecond\\rthird"', 'first\r\nsecond\rthird'),
    ('controls', '"\\a\\b\\v\\f\\0".length', '5'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_string_literals(compiler, tmp_path, value_batches, name, expression, expected, target, release):
    if name != 'constant-interpolation':
        code, output = value_batches(name, release, target, 'strings')
        assert code == '42', f'{name}: {code}\n{output}'
        assert output.encode('utf-8') == (expected + '\n').encode('utf-8')
        return
    source = tmp_path / f'{name}.dewy'
    source.write_text(f'main=():>void=>{{printl({expression})}}')
    binary = tmp_path / name
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    if name == 'constant-interpolation':
        assert 'warning:' not in built.stderr, built.stderr

    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web string checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / f'{name}.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == (expected + '\n').encode('utf-8')


@pytest.mark.parametrize(('name', 'program'), [
    ('global', 'let found=42 in? [0..100]\nlet key="a" in? ["a"->1]\nprobe=()=>if found and key 42 else 1'),
    ('array', 'probe=()=>if 42 in? [20 42] and 9 not in? [20 42] and 9 notin? [20 42] 42 else 1'),
    ('empty-array', 'probe=()=>if 42 notin? [] 42 else 1'),
    ('narrow', 'probe=()=>{let values:array<uint8>=[20 42] return if 42 in? values and 21 notin? values 42 else 1}'),
    ('record', 'probe=()=>if [x=42] in? [[x=20] [x=42]] 42 else 1'),
    ('dictionary', 'probe=()=>{let values=["a"->20 "b"->42] return if "b" in? values and "c" not in? values 42 else 1}'),
    ('string', 'probe=()=>if "é🙂" in? "café🙂!" and "missing" notin? "café🙂!" and "" in? "" 42 else 1'),
    ('order', 'let trace:int64=0\nneedle=()=>{trace=trace*10+1 return 42}\ncontainer=()=>{trace=trace*10+2 return [42]}\nprobe=()=>if needle() in? container() and trace =? 12 42 else 1'),
    ('scalar-snapshot', 'probe=()=>{let x:int64=42 let found=x in? {x=1 [42]} return if found and x =? 1 42 else 1}'),
    ('managed-snapshot', 'let needle:array<int64>=[42]\nreplace=()=>{needle=[1] return [[42]]}\nprobe=()=>if needle in? replace() and needle[0] =? 1 42 else 1'),
    ('range', 'probe=()=>if 0 in? [0..10] and 10 in? [0..10] and 10 notin? [0..10)\nand -1 notin? [0..10] and 5 notin? [10..0] and 10 in? 0..10\nand -9223372036854775808 in? [(-9223372036854775808)..9223372036854775807]\nand 9223372036854775807 in? [0..9223372036854775807] 42 else 1'),
    ('open-range', 'probe=()=>if -42 in? [..0] and 42 in? [0..] and 42 in? .. and 0 notin? [..0) 42 else 1'),
    ('range-order', 'let trace:int64=0\nneedle=()=>{trace=trace*10+1 return 0}\nlow=()=>{trace=trace*10+2 return 10}\nhigh=()=>{trace=trace*10+3 return 20}\nprobe=()=>{let found=needle() in? [low()..high()] return if not found and trace =? 123 42 else 1}'),
    ('range-snapshot', 'probe=()=>{let x:int64=3 let found=x in? [{x=99 0}..5] return if found and x =? 99 42 else 1}'),
    ('custom-default', 'Box:type=[value:int64]\nlet trace:int64=0\nneedle=()=>{trace=trace*10+1 return 21}\ncontainer=()=>{trace=trace*10+2 return Box[42]}\ncontains=(hay:Box needle:int64 extra:int64=needle):>bool=>hay.value =? needle+extra\nprobe=()=>if needle() in? container() and trace =? 12 42 else 1'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_membership(value_batches, name, program, target, release):
    code, output = value_batches(name, release, target, 'membership')
    assert code == '42', f'{name}: {code}\n{output}'


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_imported_generics(compiler, tmp_path, target, release):
    (tmp_path / 'support.dewy').write_text('''Box:type=<T>[value:T]
wrap=<T>(value:T):>Box<T>=>[value=value]
identity=<T>(value:T):>T=>value
''')
    (tmp_path / 'other.jo').write_text('''struct Box[T]:
    value: T
    extra = 2
type Nested[T] = Box[T[]]
identity[T] = (value: T) -> T: value
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''import p"support.dewy" as a
import p"other.jo" as b
from p"support.dewy" import (Box as Package), wrap
main=()=>{
    let one:a.Box<int64>=a.Box<int64>[20]
    let two=b.Box<int64>(22)
    let nested:b.Nested<string>=[value=["one"]]
    let words=Package<array<string>>[["yes"]]
    let item=wrap<string>("wrapped")
    let dewy_identity=a.identity<int64>
    let core_identity=b.identity<string>
    let make_package=wrap<int64>
    return if one.value+b.identity<int64>(two.value) =? 42 and two.extra =? 2
        and nested.value[0] =? "one" and item.value =? "wrapped"
        and dewy_identity(42) =? 42 and core_identity("ok") =? "ok"
        and make_package(42).value =? 42
        and a.identity<array<string>>(words.value)[0] =? "yes" 42 else 1
}
''')
    binary = tmp_path / 'imports'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web generic checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'imports.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('language', ['dewy', 'jo'])
@pytest.mark.parametrize('provider', ['dewy', 'jo'])
def test_core_indexed_update_order(compiler, tmp_path, target, release, language, provider):
    (tmp_path / 'store.jo').write_text('''struct Store[T]:
    values: T[]
trace = ""
at = (label: str, value: int) -> int:
    trace += label
    value
([])[T] = (s: Store[T], i: int) -> T:
    trace += "g"
    s.values[i]
([]=)[T] = (s: mut Store[T], i: int, value: T):
    trace += "s"
    s.values[i] = value
reset = (): trace = ""
events = () -> str: trace
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''from p"store.jo" import Store, at, events, reset
main=()=>{
    let root=[Store<array<int64>>[values=[[1 2]]]]
    let original=root
    root[at("a" 0)][at("b" 0)][at("c" 1)]+=at("r" 40)
    if events() not=? "abgcrs" return 1
    if root[0].values[0][1] not=? 42 or original[0].values[0][1] not=? 2 return 2
    reset()
    let store=Store<array<int64>>[values=[[1] [2]]]
    let index:int64=0
    store[index][at("c" 0)]={index=1 at("r" 42)}
    if events() not=? "grcs" or store.values[0][0] not=? 42 or store.values[1][0] not=? 2 return 3
    reset()
    let scalars=Store<int64>[values=[2 3]]
    index=0
    scalars[index]+={index=1 at("r" 40)}
    if events() not=? "grs" or scalars.values not=? [42 3] return 4
    return 42
}
''')
    if language == 'jo':
        source = tmp_path / 'main.jo'
        source.write_text('''from "store.jo" import Store, at, events, reset
change = (index: mut int, value: int) -> int:
    index = 1
    at("r", value)
main = () -> int:
    let root = [Store[int[]](values = [[1, 2]])]
    let original = root
    root[at("a", 0)][at("b", 0)][at("c", 1)] += at("r", 40)
    if events() != "abgcrs": return 1
    if root[0].values[0][1] != 42 or original[0].values[0][1] != 2: return 2
    reset()
    let store = Store[int[]](values = [[1], [2]])
    let index = 0
    store[index][at("c", 0)] = change(index, 42)
    if events() != "grcs" or store.values[0][0] != 42 or store.values[1][0] != 2: return 3
    reset()
    let scalars = Store[int](values = [2, 3])
    index = 0
    scalars[index] += change(index, 40)
    if events() != "grs" or scalars.values != [42, 3]: return 4
    42
''')
    if provider == 'dewy':
        (tmp_path / 'store.dewy').write_text('''Store:type=<T>[values:array<T>]
trace=""
at=(label:string value:int64):>int64=>{trace+=label return value}
__index__=<T>(s:Store<T> i:int64):>T=>{trace+="g" return s.values[i]}
__setindex__=<T>(@s:Store<T> i:int64 value:T):>void=>{trace+="s" s.values[i]=value}
reset=():>void=>{trace=""}
events=():>string=>trace
''')
        source.write_text(source.read_text().replace('store.jo', 'store.dewy'))
    binary = tmp_path / 'order'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web indexed update checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'order.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('name, imports', [
    ('generic-operator-arithmetic', 'Vec, __add__'),
    ('generic-operator-comparison', 'Score'),
    ('generic-operator-specialization', 'Box'),
    ('overload-group-callable', 'step, apply'),
    ('overload-group-defaults', 'choose'),
    ('overload-group-operators', 'Point'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_operator_imports(compiler, tmp_path, name, imports, target, release):
    declarations, body = CASES[name].split('main=', 1)
    (tmp_path / 'operators.dewy').write_text(declarations)
    source = tmp_path / 'main.dewy'
    source.write_text(f'from p"operators.dewy" import {imports}\nmain={body}')
    binary = tmp_path / 'operators'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web operator checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'operators.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('case', ['history', 'managed-values', 'iteration', 'capacity', 'negative-index', 'past-end'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_ring_example(compiler, tmp_path, case, target, release):
    examples = Path(__file__).resolve().parents[2] / 'examples/sloppy_core'
    shutil.copy2(examples / 'ring.dewy', tmp_path / 'ring.dewy')
    source = tmp_path / 'main.dewy'
    if case == 'history':
        source.write_text((examples / 'history.dewy').read_text())
    elif case == 'iteration':
        source.write_text('''from p"ring.dewy" import new_ring
main=()=>{
let ring=new_ring<int64>(4) loop i in [0..6) ring.push(i)
let saved=ring let sum=0 let both=0 let either=0
loop x in ring and y in [20 22] both+=x+y
loop x in ring or y in [20 22] either+=(x??0)+(y??0)
let tripled=[loop x in ring 3x]
loop x in ring {sum+=x ring.push(99)}
return if sum =? 14 and both =? 47 and either =? 56
and tripled =? [6 9 12 15] and saved[0] =? 2 and ring[0] =? 99 42 else 1
}
''')
    elif case == 'managed-values':
        source.write_text('''from p"ring.dewy" import new_ring
main=()=>{
let ring=new_ring<array<string>>(2)
loop i in [0..7) {ring.push(["{i}"])}
let snapshot=ring
ring[0][0]="changed"
ring[1]=["replacement"]
if ring[0][0] not=? "changed" or ring[1][0] not=? "replacement" return 1
if snapshot[0][0] not=? "5" or snapshot[1][0] not=? "6" return 2
let empty=new_ring<int64>(1)
if empty.len() not=? 0 return 3
empty.push(1) empty.push(42)
return if empty.len() =? 1 and empty[0] =? 42 42 else 4
}
''')
    else:
        action = {'capacity': 'new_ring<int64>(0)',
                  'negative-index': 'ring[-1]', 'past-end': 'ring[1]'}[case]
        source.write_text(f'from p"ring.dewy" import new_ring\n'
                          f'main=()=>{{let ring=new_ring<int64>(2) ring.push(42) {action} return 0}}')
    binary = tmp_path / 'ring'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web ring checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'ring.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    if case == 'history':
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == ('History length: 4\nOldest position: 6, 3\n'
                              'Newest position: 112, 6\nRewind position: 12, 6\nRecorded total: 54\n')
    elif case in ('managed-values', 'iteration'):
        assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    else:
        assert ran.returncode != 0
        message = 'ring capacity must be positive' if case == 'capacity' else 'ring index out of bounds'
        assert message in ran.stdout + ran.stderr


@pytest.mark.parametrize('case', ['stale', 'missing', 'storage-bounds', 'rhs-removes-item'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_pool_update_errors(compiler, tmp_path, case, target, release):
    declarations = ''
    setup = 'let pool:Pool<array<int64>>=[] let h=pool.add([20])'
    update = 'pool[h][0]=42'
    if case == 'stale':
        setup += ' pool.remove(h) pool.add([1])'
    elif case == 'missing':
        setup += ' h=Handle[]'
    elif case == 'storage-bounds':
        setup += ' pool.items.clear()'
    else:
        declarations = '''let pool:Pool<array<int64>>=[] let h:Handle=[]
erase=():>int64=>{pool.remove(h) return 22}
'''
        setup = 'h=pool.add([20])'
        update = 'pool[h][0]+=erase()'
    source = tmp_path / 'invalid.dewy'
    source.write_text(declarations + f'main=()=>{{{setup} {update} return 0}}')
    binary = tmp_path / 'invalid'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web pool update checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'invalid.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode != 0, 'invalid pool update unexpectedly succeeded'
    expected = 'out of bounds' if case == 'storage-bounds' else 'gone from the pool'
    assert expected in ran.stdout + ran.stderr


@pytest.mark.parametrize('setter', [False, True], ids=['missing-setter', 'readonly-receiver'])
def test_core_indexed_update_rejects(compiler, tmp_path, setter):
    source = tmp_path / 'readonly.jo'
    source.write_text('''struct Store:
    values: int[][]
([]) = (s: Store, i: int) -> int[]: s.values[i]
''' + ('([]=) = (s: mut Store, i: int, value: int[]): s.values[i] = value\n' if setter else '') + '''edit = (s: Store):
    s[0][0] = 42
main = ():
    edit(Store(values = [[1]]))
''')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'readonly'],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode != 0, 'a getter copy must not silently discard the update'
    expected = 'read-only' if setter else '[]='
    assert expected in built.stderr, built.stdout + built.stderr


@pytest.mark.parametrize('operator', ['//', '%'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('type_name', ['int64', 'uint64'])
def test_core_floor_zero_divisor(compiler, tmp_path, operator, target, release, type_name):
    source = tmp_path / 'zero.dewy'
    # Runtime zero prevents a constant-folding diagnostic from substituting for
    # the generated program's division-by-zero behavior.
    source.write_text(f'main=()=>{{let zero:{type_name}=(args().length-1) as {type_name} '
                      f'return (42 as {type_name}) {operator} zero}}')
    binary = tmp_path / 'zero'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web arithmetic checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'zero.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode != 0, 'zero divisor unexpectedly returned successfully'


@pytest.mark.parametrize('name', CHECKSUMS_1000)
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_applications(compiler, tmp_path, name, target, release):
    source = prepare_source(name, tmp_path)
    binary = tmp_path / name
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary, '1000']
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web application checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / f'{name}.cjs'
        runner.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [node, runner, '1000']
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    checksum, elapsed = map(int, ran.stdout.split())
    assert checksum == CHECKSUMS_1000[name]
    assert elapsed >= 0


@pytest.mark.parametrize('body, diagnostic', [
    ('let xs=[10 20] let low:int64=-1 loop value in xs[low..] return', 'slice'),
    ('let xs=[10 20] loop value in xs[0..3) return', 'slice'),
    ('let xs=[10 20] loop value in xs[2..1) return', 'slice'),
    ('let xs=[10 20] loop value in xs[3..3) return', 'slice'),
    ('let xs=[10 20] let high=int64.max loop value in xs[0..high] return', 'slice'),
    ('let xs=[10 20] loop i in (-1).. and i <? xs.length {printl(xs[i])}', 'out of bounds'),
    ('let xs=[10 20] loop i in 0.. and i <? xs.length {printl(xs[i+1])}', 'out of bounds'),
    ('let xs=[10 20 30] let stop=xs.length loop i in 0.. and i <? stop {xs.pop() printl(xs[i])}', 'out of bounds'),
    ('let xs:array<int64>=[] printl(xs[end])', 'out of bounds (length 0)'),
    ('let text="" printl(text[end])', 'string index out of bounds'),
    ('let xs=[10 20] xs[0..2]=42', 'range indexes are out of bounds'),
    ('let xs=[10 20] xs[..]=[42]', 'values for 2 range indexes'),
    ('let xs=[10 20] xs[-1..1]=42', 'range index -1 is out of bounds'),
    ('let xs=[10 20] printl(xs[0,0..1])', 'range step must be nonzero'),
    ('let xs=[10 20] printl(xs[[0,2..2]])', 'range indexes are out of bounds'),
    ('let xs=[10 20] xs[0,2..4]=42', 'range indexes are out of bounds'),
    ('let xs=[10 20] printl(xs[[1,0..-1]])', 'range indexes are out of bounds'),
    ('let xs=[10 20] xs[[0..1]]=[42]', 'values for 2 range indexes'),
    ('let xs=[10 20] printl(xs[IntRange[0 9223372036854775808 3 true false]])', 'range indexes are out of bounds'),
    ('let xs=[10 20] printl(xs[IntRange[0 1 0 true false]])', 'range indexes are out of bounds'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_range_index_errors(error_batches, body, diagnostic, target, release):
    ran = error_batches('range', body, release, target)
    assert ran.returncode != 0 and diagnostic in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('body', [
    'const [x y]:array<int64>=[42] printl(x+y)',
    'let [x y]:array<int64>=[42] printl(x+y)',
    'let sum=([x y]:array<int64>)=>x+y printl(sum([42]))',
    'let sum=([[x y]]:array<array<int64>>)=>x+y printl(sum([[42]]))',
    'loop [x y] in [[1] [2 3]] {printl(x+y)}',
    'loop [key [x y]] in ["a"->[1]] {printl(x+y)}',
    'loop i in [0..1) and [[x y]] in [[[1]]] {printl(x+y)}',
    'let values:dict<string int64>=[] let [[_ x] [_ y]]=values printl(x+y)',
    'let [[_ x] [_ y]]=["one"->42] printl(x+y)',
    'let [[_ x] [_ y]]=["one"->20 "two"->22 "three"->99] printl(x+y)',
    'let [[_ [x y]]]=["one"->[42]] printl(x+y)',
    'let [x y]=set[42] printl(x+y)',
    'let [x y]=set[1 2 3] printl(x+y)',
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_unpack_errors(error_batches, body, target, release):
    ran = error_batches('unpack', body, release, target)
    assert ran.returncode != 0 and 'unpacking requires exactly 2 elements' in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('body', [
    'loop [x] in [[1 2]] {printl(x)}',
    'loop i in [0..1) and [x] in [[1 2]] {printl(x)}',
    'let values=[loop [x] in [[1 2]] x] printl(values)',
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_unpack_single_errors(error_batches, body, target, release):
    ran = error_batches('unpack', body, release, target)
    assert ran.returncode != 0 and 'unpacking requires exactly 1 elements' in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('body, diagnostic', [
    ('let xs:array<int64 length=2>=[20 22] xs[0..2]=0', 'range indexes are out of bounds'),
    ('let xs:array<int64 length=2>=[20 22] xs[-1..1]=0', 'range index -1 is out of bounds'),
    ('let xs:array<int64 length=2>=[20 22] xs[..]=[0]', 'values for 2 range indexes'),
    ('let xs:array<int64 length=2>=[20 22] xs[0,0..1]=0', 'range step must be nonzero'),
    ('let xs:array<int64 length=2>=[20 22] xs[[2]]=0', 'out of bounds'),
    ('let xs:array<int64 length=2>=[20 22] xs[[true]]=0', 'a mask of 1 for 2 elements'),
    ('let xs:array<int64 length=2>=[20 22] xs[[true false]]=[0 0]', 'values for the 1 elements in the mask'),
    ('let xs:array<int64 length=2>=[20 22] xs[[0 1]]=[0]', 'values for 2 indexes'),
    ('let values=[20 22] let mask:array<bool length=1>=[true] printl(values[mask])', 'a mask of 1 for 2 elements'),
    ('let values:array<int64 length=2>=[20 22] let indexes:array<int64 length=1>=[2] values[indexes]=0', 'out of bounds'),
    ('let input=[20] let pair:array<int64 length=2>=input printl(pair)', 'fixed-size array needs 2 elements'),
    ('let input=[20 22 99] printl(input as array<int64 length=2>)', 'fixed-size array needs 2 elements'),
    ('let input:array<string>=[] let pair:array<string length=2>=input printl(pair)', 'fixed-size array needs 2 elements'),
    ('let rows:array<array<int64 length=2>>=[] printl(rows[args().length].length)', 'out of bounds'),
    ('let values:array<int64 length=2>=[20 22] let stop=args().length+3 printl(values[0..stop))', 'slice'),
    ('let values:array<int64 length=2>=[20 22] printl(values[2..1))', 'slice'),
    ('let values:array<int64 length=2>=[20 22] let first=0-args().length-1 printl(values[first..1))', 'slice'),
    ('let values:array<uint8 length=2>=[20 22] let triple:array<uint8 length=3>=[values...] printl(triple)', 'fixed-size array needs 3 elements'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_fixed_array_errors(error_batches, body, diagnostic, target, release):
    ran = error_batches('bounds', body, release, target)
    assert ran.returncode != 0 and diagnostic in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('body, diagnostic', [
    ('printl([1 2] .+ [1 2 3])', 'shapes do not match'),
    ('printl(__grapheme_word([0 0 0] 0))', 'grapheme table word out of bounds'),
    ('printl(__grapheme_word([0 0 0 0] 1))', 'grapheme table word out of bounds'),
    ('let offset=0-args().length printl(__grapheme_word([0 0 0 0] offset))', 'grapheme table word out of bounds'),
    ('let a=[1 2 3] let b=[4 5] printl([loop i in [0..a.length) a[i]+b[i]])', 'out of bounds'),
    ('let xs=[1 2] xs .+= [1 2 3]', 'shapes do not match'),
    ('let xs:array<int64 length=1>=[1] xs .+= [1 2]', 'fixed-size array needs 1 elements'),
    ('let xs=[1 2] xs[0..0] .+= [10 20]', 'values for 1 range indexes'),
    ('let xs=[1 2] xs[[true false]] .+= [10 20]', 'values for the 1 elements in the mask'),
    ('let xs=[1 2] xs[[0]] .+= [10 20]', 'values for 1 indexes'),
    ('let xs=[1 2] xs[0,0..1] .+= 10', 'range step must be nonzero'),
    ('let xs=[1 2] right=($capture @xs)=>{xs.pop() return 10} xs[..] .+= right()', 'out of bounds'),
    ('let xs=[1 2] right=()=>{panic("RHS evaluated") return 10} xs[[2]] .+= right()', 'out of bounds'),
    ('let xs=[1 2] xs[[true]] .+= 10', 'a mask of 1 for 2 elements'),
    ('let m=zeros(2 3) m[[..] 1] .+= [1.0 2.0 3.0]', 'do not match for an elementwise operation'),
    ('let m=zeros(2 3) m[[0..0] 1] .+= [1.0 2.0]', 'assigning 2 elements to a part of 1'),
    ('let m=zeros(2 3) right=($capture @m)=>{m=zeros(1 1) return 1.0} m[[..] [..]] .+= right()', 'out of bounds'),
    ('let m=zeros(2 3) right=()=>{panic("RHS evaluated") return 1.0} m[[..] 3] .+= right()', 'out of bounds'),
    ('printl(zeros(2 3) .+ [1.0 2.0])', 'do not match for an elementwise operation'),
    ('printl(zeros(0 3) .+ zeros(2 3))', 'do not match for an elementwise operation'),
    ('let m=zeros(0 3) printl(m[end 0])', 'out of bounds'),
    ('let m=zeros(2 0) printl(m[0 end])', 'out of bounds'),
    ('let m=zeros(2 3) printl(m[[..] 3])', 'out of bounds'),
    ('let m=zeros(2 3) printl(m[[..] [0..4)])', 'out of bounds'),
    ('let m=zeros(2 3) printl(m[[..] [0,0..2]])', 'range step must be nonzero'),
    ('let m=zeros(2 3) let r=[2,1..-1] printl(m[[..] r])', 'out of bounds'),
    ('let m=zeros(2 3) let r=IntRange[0 9223372036854775808 3 true false] printl(m[[..] r])', 'out of bounds'),
    ('let m=zeros(2 3) let r=IntRange[0 1 0 true false] printl(m[[..] r])', 'out of bounds'),
    ('let m=zeros(2 3) right=($capture @m)=>{m=zeros(2 2) return 1.0} m[[..] [2,0..0]] .+= right()', 'out of bounds'),
    ('let m=zeros(2 3) m[[..] 1]=[1.0]', 'assigning 1 elements to a part of 2'),
    ('let m=zeros(2 3) printl(m[[..] [..] 0])', '3 indexes for an array'),
    ('printl(fill(0 (1<<61)+1).length)', 'array is too large'),
    ('let xs:array<int64>=[] xs.reserve((1<<61)+1)', 'array is too large'),
    ('let xs=[1] xs.reserve((1<<61)+1)', 'array is too large'),
    ('printl(zeros(1<<32 1<<32).shape)', 'array shape is too large'),
    ('printl(ones(1<<32 2 1<<31).shape)', 'array shape is too large'),
    ('printl(zeros<int64>(1<<32 1<<32).shape)', 'array shape is too large'),
    ('printl(rand(1<<32 1<<32).shape)', 'array shape is too large'),
    ('printl(randn(1<<32 1<<32).shape)', 'array shape is too large'),
    ('let xs:array<int64>=[] printl(reshape(xs 1<<32 1<<32))', 'array shape is too large'),
    ('printl(zeros(1<<32 0)*zeros(0 1<<32))', 'array shape is too large'),
    ('printl(zeros(-2 -3))', 'array dimensions must be nonnegative'),
    ('printl(ones(0 -1))', 'array dimensions must be nonnegative'),
    ('printl(zeros<int64>(2 -1 3))', 'array dimensions must be nonnegative'),
    ('printl(rand(-1 2))', 'array dimensions must be nonnegative'),
    ('printl(randn(2 -1))', 'array dimensions must be nonnegative'),
    ('printl(reshape([1 2] 2 2))', 'elements do not make an array'),
    ('printl(zeros(2 3)*zeros(2 3))', 'inner sizes differ'),
    ('let m=zeros(2 3) printl(m[0 3])', 'out of bounds'),
    ('printl(solve(zeros(2 2) [1.0 2.0]))', 'matrix has no inverse'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_array_errors(error_batches, body, diagnostic, target, release):
    ran = error_batches('bounds', body, release, target)
    assert ran.returncode != 0 and diagnostic in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('body', [
    'printl(fill(0 (1<<29)+1).length)',
    'let xs:array<uint8>=[] xs.reserve(1<<32)',
    'printl(zeros(1<<16 1<<16).shape)',
])
@pytest.mark.parametrize('target', ['wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_web_array_size_errors(error_batches, body, target, release):
    ran = error_batches('bounds', body, release, target)
    assert ran.returncode != 0 and 'array is too large' in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_example(compiler, tmp_path, target, release):
    source = Path(__file__).resolve().parents[2] / 'examples/sloppy_core/trajectory_fit.dewy'
    command, error = build_case_batch(compiler, tmp_path, {'trajectory': source.read_text()},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == ('height = 1.501 + 8.008*t + -4.909*t*t\n'
                          'height at 0.6 seconds: 4.538\n')


@pytest.mark.parametrize('target, backend', [
    ('native', 'fallback'), ('wasm', 'fallback'),
    ('native', 'gles'), ('native', 'vulkan'),
])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_gpu_arrays(compiler, tmp_path, target, backend, release, request):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_THREADS='2', LP_NUM_THREADS='2', SLOPPY_VK_PIPELINE_CACHE='0')
    if backend == 'fallback':
        env['SLOPPY_SOFTWARE'] = '1'
    else:
        if platform.system() != 'Linux':
            pytest.skip('offscreen Mesa driver checks currently target Linux')
        env.update(LIBGL_ALWAYS_SOFTWARE='1', EGL_PLATFORM='surfaceless')
        if backend == 'gles':
            request.getfixturevalue('shader_driver')
            env['SLOPPY_VULKAN'] = '0'
        else:
            drivers = list(Path('/usr/share/vulkan/icd.d').glob('lvp_icd*.json'))
            drivers = [path for path in drivers if 'i686' not in path.name]
            if not drivers:
                pytest.skip('Mesa lavapipe Vulkan driver is needed')
            env.update(SLOPPY_VULKAN='1', VK_DRIVER_FILES=str(drivers[0]),
                       VK_ICD_FILENAMES=str(drivers[0]))
    program = '''import p"@lib/game/gpuarray.jo" as engine
half=(x:float32):>float32=>x*0.5+0.25
main=()=>{
printl"{gpu_available()} {engine.__gpu_vk}"
let original=[1.0 2.0 3.0 4.0] let g=gpu(original) let saved=g
original[0]=99.0
let h=half.(g) .* 2.0 .+ 1.0
assert(cpu(h).data =? [2.5 3.5 4.5 5.5])
assert(cpu(.-(half.(g) .* 2.0 .+ 1.0)).data =? [-2.5 -3.5 -4.5 -5.5])
assert(cpu(.+g).data =? [1.0 2.0 3.0 4.0])
assert(cpu(hypot.(gpu([3.0 5.0]) gpu([4.0 12.0]))).data =? [5.0 13.0])
let magnitudes=cpu(hypot.(gpu([3e30 3e-30 0.0 -3e30 INF NAN NAN])
                         gpu([4e30 4e-30 -0.0 4e30 NAN INF 1.0]))).data
assert(abs(magnitudes[0]/5e30-1.0) <? 1e-6)
assert(abs(magnitudes[1]/5e-30-1.0) <? 1e-6)
assert(magnitudes[2] =? 0.0 and 1.0/magnitudes[2] >? 0.0)
assert(abs(magnitudes[3]/5e30-1.0) <? 1e-6)
assert(magnitudes[4] =? INF and magnitudes[5] =? INF and is_nan(magnitudes[6]))
let zeros=cpu(.-gpu([0.0 -0.0])).data
assert(1.0/zeros[0] <? 0.0 and 1.0/zeros[1] >? 0.0)
assert(sum(h) =? 16.0 and min(h) =? 2.5 and max(h) =? 5.5)
assert(cpu(g .>? 2.0).data =? [0.0 0.0 1.0 1.0])
let m=gpu(reshape([1.0 2.0 3.0 4.0 5.0 6.0] 2 3))
let row=gpu([10.0 20.0 30.0]) let col=gpu(reshape([100.0 200.0] 2 1))
let result=cpu(m .+ row .+ col)
assert(result.shape =? [2 3] and result.data =? [111.0 122.0 133.0 214.0 225.0 236.0])
assert(cpu(m ./ 2.0).data =? [0.5 1.0 1.5 2.0 2.5 3.0])
let ints=gpu([-7 0 9])
assert(cpu(ints .* 2 .+ 1).data =? [-13 1 19])
assert(cpu(.-ints).data =? [7 0 -9])
assert(cpu(.+ints).data =? [-7 0 9])
assert(sum(ints) =? 2 and min(ints) =? -7 and max(ints) =? 9)
let empty=gpu(zeros(0 3)) .+ row
assert(cpu(empty).shape =? [0 3] and size(cpu(empty)) =? 0 and sum(empty) =? 0.0)
let many=gpu(fill(1.0 4097)) .* 3.0
assert(sum(many) =? 12291.0 and min(many) =? 3.0 and max(many) =? 3.0)
loop i in [0..24) {g .+= 0.5}
assert(cpu(g).data =? [13.0 14.0 15.0 16.0])
assert(cpu(saved).data =? [1.0 2.0 3.0 4.0])
let downloaded=cpu(saved) downloaded[0]=123.0
assert(cpu(saved).data =? [1.0 2.0 3.0 4.0])
return 0
}'''
    example = Path(__file__).resolve().parents[2] / 'examples/sloppy_core/terrain_array.dewy'
    command, error = build_case_batch(compiler, tmp_path, {'gpu': program, 'terrain': example.read_text()},
                                      ['exit(case_0()+case_1())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    expected = {'fallback': 'false false\n', 'gles': 'true false\n', 'vulkan': 'true true\n'}
    available = 'false' if backend == 'fallback' else 'true'
    assert ran.stdout.startswith(expected[backend] +
                                f'Generated 33x33 height field (GPU available: {available}).\n'), ran.stdout + ran.stderr
    assert ran.stdout.splitlines()[2].startswith('Maximum CPU difference: '), ran.stdout


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_metal_magnitude(compiler, tmp_path, release):
    # Source cross-compilation only: execution requires Apple hardware.
    source = tmp_path / 'magnitude.dewy'
    source.write_text('main=()=>{printl(cpu(hypot.(gpu([3.0]) gpu([4.0]))).data) return 0}')
    shaders = tmp_path / 'shaders'
    shaders.mkdir()
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_MSL_DUMP'] = str(shaders)
    built = subprocess.run([compiler, 'build', source, '--target', 'macos', '-o', tmp_path / 'magnitude',
                            *(['--release'] if release else [])], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    kernels = list(shaders.glob('*.kernel.metal'))
    assert len(kernels) == 1
    text = kernels[0].read_text()
    assert 'float sl_hypot(float x, float y)' in text
    assert 'as_type<uint>(x)' in text and 'as_type<float>(max(hi &' in text
    assert 'f64_bits' not in text and 'floatBitsToUint' not in text


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_metal_unary_plus(compiler, tmp_path, release):
    # Cross-compilation checks generated source; executing Metal needs macOS.
    source = tmp_path / 'plus.dewy'
    source.write_text('''main=()=>{
let floats=.+gpu([1.0 2.0]) let ints=.+gpu([1 -2])
printl(cpu(floats).data) printl(cpu(ints).data)
return 0
}''')
    shaders = tmp_path / 'shaders'
    shaders.mkdir()
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_MSL_DUMP'] = str(shaders)
    built = subprocess.run([compiler, 'build', source, '--target', 'macos', '-o', tmp_path / 'plus',
                            *(['--release'] if release else [])], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    kernels = sorted(shaders.glob('*.kernel.metal'))
    assert len(kernels) == 2
    for kernel in kernels:
        text = kernel.read_text()
        bodies = re.findall(r'(?:float|int) f_\w+\([^)]*\)\s*\{([^}]+)\}', text)
        assert len(bodies) == 1, text
        assert '~' not in bodies[0], text
        assert re.search(r'\breturn l_\w+;', bodies[0]), text


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_pointer_loop_aliases(compiler, tmp_path, target, release):
    (tmp_path / 'loops.jo').write_text('''axpy[T] = (left: mut T[], right: T[], scale: T):
    assert(left.len() == right.len())
    p = data(left)
    q = data(right)
    loop i in [0..left.len()): p[i] += scale * q[i]
overlap[T] = (values: mut T[]):
    p = data(values)
    q = p + 1
    loop i in [0..max(values.len() - 1, 0)): q[i] += p[i]
same[T] = (values: mut T[]):
    p = data(values)
    q = p
    loop i in [0..values.len()): q[i] += p[i]
ordered = (values: f64[]) -> f64:
    p = data(values)
    total = 0.0
    loop i in [0..values.len()): total += p[i]
    total
''')
    program = '''from p"loops.jo" import axpy, overlap, same, ordered
exercise=<T>(one:T):>void=>{
loop count in [0..20) {
    let a=fill(one count) let b=fill(one+one count) let saved=a
    axpy(@a b one+one)
    loop v in a {assert(v =? one+one+one+one+one)}
    loop v in saved {assert(v =? one)}
    let ascending=fill(one count)
    overlap(@ascending)
    loop i in [0..count) {assert(ascending[i] =? ((i+1) as T))}
    same(@ascending)
    loop i in [0..count) {assert(ascending[i] =? ((2*(i+1)) as T))}
}
}
main=()=>{
exercise<float64>(1.0) exercise<float32>(1.0)
assert(ordered([1e16 1.0 -1e16 2.0]) =? 2.0)
return 42
}'''
    command, error = build_case_batch(compiler, tmp_path, {'loops': program},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    modes = [False, True] if target == 'native' else [False]
    for no_avx in modes:
        env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
        if no_avx:
            env['SLOPPY_NO_AVX'] = '1'
        ran = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10, check=False)
        assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('flags', [[], ['--release']], ids=['default', 'release'])
def test_core_numeric_cpu_feature_initializer(compiler, tmp_path, flags):
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('the vectorizer currently targets native x86-64')
    source = tmp_path / 'matrix.dewy'
    source.write_text('main=()=>{let a=ones(2 2) return sum(a*a) as int64}')
    binary = tmp_path / 'matrix'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    # Merely reserving the vectorizer's global leaves it zero: its runtime
    # initializer must stay reachable without an explicit reference in user code.
    assert 'fn f___cpu_detect_' in built.stdout
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 8, ran.stdout + ran.stderr


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_array_vectors(compiler, tmp_path, release):
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('AVX2/SSE2 code generation targets native x86-64')
    source = tmp_path / 'vectors.dewy'
    source.write_text('''looped=<T>(a:array<T> b:array<T>):>array<T>=>[loop i in [0..a.length) a[i]*2.0+b[i]*0.5+1.0]
valued=<T>(a:array<T> b:array<T>):>array<T>=>[loop i in 0.. and x in a x*2.0+b[i]*0.5+1.0]
mapped=<T>(a:array<T>):>array<T>=>[loop x in a x*2.5+1.0]
fused=<T>(a:array<T> b:array<T>):>array<T>=>a .* 2.0 .+ b .* 0.5 .+ 1.0
negated=<T>(a:array<T>):>array<T>=>.-a
negloop=<T>(a:array<T>):>array<T>=>[loop x in a -x]
main=(argv:array<string>)=>{
let words64:array<uint64>=[0 0x8000000000000000 0x7ff0000000000000 0xfff0000000000000 0x7ff8000000000042 0xfff8000000000017 1 0x3ff4000000000000]
let words32:array<uint32>=[0 0x80000000 0x7f800000 0xff800000 0x7fc00042 0xffc00017 1 0x3fa00000]
loop n in [0..20) {
let a=[loop i in [0..n) (i as float64)*0.5]
let b=[loop i in [0..n) (i as float64)*0.25]
let expected=[loop i in [0..n) (i as float64)*1.125+1.0]
assert(looped(a b) =? expected and fused(a b) =? expected)
assert(valued(a b) =? expected)
let same=[loop i in [0..n) (i as float64)*1.25+1.0]
assert(looped(a a) =? same and fused(a a) =? same)
assert(valued(a a) =? same and mapped(a) =? same)
let single_a=float32.(a) let single_b=float32.(b)
let single_expected=float32.(expected)
assert(looped(single_a single_b) =? single_expected and fused(single_a single_b) =? single_expected)
assert(valued(single_a single_b) =? single_expected and mapped(single_a) =? float32.(same))
let special64=[loop i in [0..n) f64_from_bits(words64[i%8])]
let special32=[loop i in [0..n) f32_from_bits(words32[i%8])]
let negative64=negated(special64) let loop64=negloop(special64)
let negative32=negated(special32) let loop32=negloop(special32)
loop i in [0..n) {
assert(f64_bits(negative64[i]) =? (words64[i%8] xor 0x8000000000000000))
assert(f64_bits(loop64[i]) =? f64_bits(negative64[i]))
assert(f32_bits(negative32[i]) =? (words32[i%8] xor 0x80000000))
assert(f32_bits(loop32[i]) =? f32_bits(negative32[i]))
}
}
if argv.length >? 1 {
if argv[1] =? "values" printl(valued(fill(1.0 20) fill(2.0 19)))
else printl(looped(fill(1.0 20) fill(2.0 19)))
}
return 42
}''')
    binary = tmp_path / 'vectors'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    bodies = [body for body in re.split(r'(?=^fn )', built.stdout, flags=re.M)
              if re.match(r'fn f_(?:looped|fused|valued|mapped|negated|negloop)_', body)]
    assert len(bodies) == 12, built.stdout
    assert all('vld ' in body and 'vst ' in body for body in bodies), '\n'.join(bodies)
    for sse2 in [False, True]:
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('DEWY_', 'SLOPPY_'))}
        if sse2:
            env['SLOPPY_NO_AVX'] = '1'
        ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=10, check=False)
        assert ran.returncode == 42, ran.stdout + ran.stderr
        for form in ['short', 'values']:
            short = subprocess.run([binary, form], env=env, capture_output=True, text=True,
                                   timeout=10, check=False)
            assert short.returncode != 0 and 'out of bounds' in short.stderr, short.stdout + short.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_ranges_custom_index(compiler, tmp_path, target, release):
    (tmp_path / 'lookup.jo').write_text('''struct Lookup:
    value: int
calls = 0
len = (x: Lookup) -> int:
    calls += 1
    x.value
count = () -> int: calls
([]) = (x: Lookup, a: int, b: int) -> int: a + b
([]=) = (x: mut Lookup, a: int, b: int, value: int): x.value = value + a + b
([]) = (x: Lookup, a: IntRange, b: IntRange) -> int: x.value + a._first + b._first
([]=) = (x: mut Lookup, a: IntRange, b: IntRange, value: int): x.value = value + a._first + b._first
''')
    program = '''from p"lookup.jo" import Lookup, count
main=()=>{
let x=Lookup[10]
assert(x[[1..3] (1..3]] =? 13)
x[[1,3..5] [4,2..0]]=37
let other=Lookup[22]
assert(other[end end] =? 42 and count() =? 1)
other[end end]=0
assert(other.value =? 42 and count() =? 2)
return x.value
}'''
    command, error = build_case_batch(compiler, tmp_path, {'custom_index': program},
                                      ['exit(case_0())'], release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('body, diagnostic', [
    ('let values=set[20] printl(values.pop(22))', 'the set has no member 22'),
    ('let values:set<int64>=set[] printl(values.pop())', 'cannot pop an empty set'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_set_errors(error_batches, body, diagnostic, target, release):
    ran = error_batches('set', body, release, target)
    assert ran.returncode != 0 and diagnostic in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('body, diagnostic', [
    ('let value=42 value//=0', 'division by zero'),
    ('let value=-42 value%=0', 'division by zero'),
    ('let value=3/2 value/=0', 'division by zero'),
    ('let value=2 value^=(-1)', 'negative integer exponent'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_compound_errors(error_batches, body, diagnostic, target, release):
    ran = error_batches('compound', body, release, target)
    assert ran.returncode != 0 and diagnostic in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('body, diagnostic', [
    ('printl(format(1.25 "."))', 'precision needs digits'),
    ('printl(format(1.25 "x"))', 'does not apply'),
    ('printl(format(42 ".2x"))', 'precision needs a floating-point format'),
    ('printl(format(42 "dextra"))', 'unexpected text after format'),
    ('printl(format(42 "99999999999999999999999"))', 'format width is too large'),
    ('printl(format(1.25 ".99999999999999999999999f"))', 'format precision is too large'),
    ('printl(format("hello" ".2s"))', 'numeric flags and precision need a number'),
    ('printl(format("hello" "+5"))', 'numeric flags and precision need a number'),
    ('printl(format("hello" "x"))', 'does not apply'),
    ('printl(format(1.25 "#.2f"))', 'alternate prefix needs an integer base'),
    ('printl(format(12345 "_x"))', 'digit grouping needs a decimal format'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_format_errors(error_batches, body, diagnostic, target, release):
    ran = error_batches('format', body, release, target)
    assert ran.returncode != 0 and diagnostic in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('body', [
    'let xs=[1 2] let shrink=($capture @xs)=>xs.clear() loop @x in xs {shrink() x+=1}',
    'let xs=[[1] [2]] let shrink=($capture @xs)=>xs.clear() loop @x in xs {shrink() x.push(3)}',
])
def test_core_mutable_loop_errors(error_batches, body, target, release):
    ran = error_batches('bounds', body, release, target)
    assert ran.returncode != 0 and 'out of bounds' in ran.stdout + ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('name', quick_parameters(ERRORS, QUICK_ERRORS))
def test_core_rejects(compiler, tmp_path, name):
    body, diagnostic = ERRORS[name]
    source = tmp_path / f'{name}.dewy'
    source.write_text(body)
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode != 0 and diagnostic in built.stderr, built.stdout + built.stderr
    assert os.path.normcase(str(source)) in os.path.normcase(built.stderr)
    assert not binary.exists()


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
@pytest.mark.parametrize('style', ['selected', 'namespace', 'module-alias', 'name-alias'])
@pytest.mark.core_quick
def test_core_imports(compiler, tmp_path, extension, style):
    dependency = tmp_path / f'helper.{extension}'
    dependency.write_text('twice=(x:int64):>int64=>x*2' if extension == 'dewy'
                          else 'twice = (x: int) -> int: x * 2')
    source = tmp_path / 'main.dewy'
    forms = {
        'selected': (f'from p"helper.{extension}" import twice', 'twice(21)'),
        'namespace': (f'import p"helper.{extension}"', 'helper.twice(21)'),
        'module-alias': (f'import p"helper.{extension}" as other', 'other.twice(21)'),
        'name-alias': (f'from p"helper.{extension}" import twice as double', 'double(21)'),
    }
    declaration, expression = forms[style]
    source.write_text(f'{declaration}\nmain=():>int64=>{expression}')
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
def test_core_imported_dependent_default(compiler, tmp_path, extension):
    dependency = tmp_path / f'helper.{extension}'
    dependency.write_text('let offset:int64=2\ncombine=(a:int64 b:int64=a+offset)=>a+b'
                          if extension == 'dewy' else
                          'offset: int = 2\ncombine = (a: int, b: int = a + offset) -> int: a + b\n')
    source = tmp_path / 'main.dewy'
    source.write_text(f'''from p"helper.{extension}" import combine
let offset:int64=99
main=()=>{{let value:int64=20 return combine(value)}}''')
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_inline_record_across_modules(compiler, tmp_path, release):
    (tmp_path / 'helper.dewy').write_text('''Count:type=int64
make=():>[y:Count x:Count]=>[x=20 y=22]
sum=(point:[x:Count y:Count])=>point.x+point.y
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''from p"helper.dewy" import make, sum
Count:type=string
main=()=>{let point:[x:int64 y:int64]=make()
return if sum([y=22 x=20]) =? 42 point.x+point.y else 1}
''')
    binary = tmp_path / 'main'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
def test_core_imported_record_brackets(compiler, tmp_path, extension):
    dependency = tmp_path / f'helper.{extension}'
    dependency.write_text('Point:type=[x:int64=20 y:int64=22]' if extension == 'dewy'
                          else 'struct Point:\n    x: int = 20\n    y: int = 22\n')
    source = tmp_path / 'main.dewy'
    source.write_text(f'''import p"helper.{extension}" as geometry
from p"helper.{extension}" import Point
main=()=>{{let p=geometry.Point[20 22] let q=Point[y=22 x=20] return p.x+q.y}}''')
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


class Scripts(HTMLParser):
    """Extract the generated web runner, which also supports Node execution."""

    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.inside = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_rollback_model(compiler, tmp_path, target, release):
    source = Path(__file__).resolve().parents[2] / 'core/tests/rollback.dewy'
    binary = tmp_path / 'rollback'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web rollback checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'rollback.cjs'
        runner.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [node, runner]
    for scenario in ['direct', 'delayed']:
        ran = subprocess.run([*command, scenario], capture_output=True, text=True,
                             timeout=15, check=False)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert not ran.stderr, ran.stderr
        lines = ran.stdout.splitlines()
        assert len(lines) == 8, ran.stdout
        tick = int(lines[0])
        assert 700 < tick < 900
        positions, scores = [0, 0], [0, 0]
        for t in range(2, tick):
            for player in range(2):
                positions[player] += (t//12 + player) % 3 - 1
                if (t + player*3) % 11 == 0 and abs(positions[player] - positions[1-player]) < 5:
                    scores[player] += 1
        expected = {'positions': positions, 'scores': scores, 'hits': sum(scores)}
        assert json.loads(lines[1]) == json.loads(lines[2]) == expected
        rollbacks = list(map(int, lines[3:5]))
        if scenario == 'delayed':
            assert all(n > 30 for n in rollbacks)
        else:
            assert rollbacks == [0, 0]
        assert lines[5:7] == ['-1', '-1']
        assert json.loads(lines[7]) == {'positions': [0, 0], 'scores': [0, 0], 'hits': 0}


@pytest.mark.parametrize(('setup', 'callback', 'start', 'diagnostic'), [
    ('tick=(state:int64 _inputs:array<int64>)=>state+int64(time())', 'tick', '0', 'reads the clock'),
    ('clock=()=>time()\ntick=(state:int64 _inputs:array<int64>)=>state+int64(clock())', 'tick', '0', 'reads the clock'),
    ('', '((state:int64 _inputs:array<int64>)=>state+int64(random()))', '0', 'takes random numbers'),
    ('let count=0\nhelper=()=>{count+=1 return count}\ntick=(state:int64 _inputs:array<int64>)=>state+helper()', 'tick', '0', "changes the global 'count'"),
    ('input=()=>if key_down(Key.space) 1 else 0\ntick=(state:int64 _inputs:array<int64>)=>state+input()', 'tick', '0', 'reads the input'),
    ('helper=(n:int64):>int64=>if n>?0 helper(n-1) else int64(time())\ntick=(state:int64 _inputs:array<int64>)=>state+helper(1)', 'tick', '0', 'reads the clock'),
    ('tick=(state:Rng _inputs:array<int64>)=>{state.next_int(0 10) return state}', 'tick', 'rng(7)', None),
    ('tick=(state:Rng _inputs:array<int64>)=>{let xs=[1 2 3] shuffle(@state @xs) return state}', 'tick', 'rng(7)', None),
    ('tick=(state:int64 _inputs:array<int64>)=>state+int64(unix_time(date(0.0 utc=true)))', 'tick', '0', None),
    ('let random_state=rng(7)\ntick=(state:int64 _inputs:array<int64>)=>state+random_state.next_int(0 10)', 'tick', '0', "changes the global 'random_state'"),
    ('random=(value:int64)=>value\ntick=(state:int64 _inputs:array<int64>)=>state+random(1)', 'tick', '0', None),
    ('tick=(state:int64 inputs:array<int64>)=>state+inputs[0]+inputs[1]', 'tick', '0', None),
], ids=['clock', 'helper-clock', 'lambda-random', 'helper-global', 'helper-input', 'recursive-clock', 'seeded-rng', 'seeded-shuffle', 'date-conversion', 'global-rng', 'user-random', 'pure'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('at_top', [False, True], ids=['main', 'global'])
def test_core_netplay_tick_warnings(compiler, tmp_path, setup, callback, start, diagnostic, target, release, at_top):
    source = tmp_path / 'tick.dewy'
    session = f'let game=netplay.session({start} {callback} players=2 me=0)'
    program = f'{session}\nmain=()=>game.tick+42' if at_top else f'main=()=>{{{session} return game.tick+42}}'
    source.write_text(f'import netplay\n{setup}\n{program}')
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', tmp_path / 'tick', *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    outputs = [built.stderr]
    if target == 'native' and not release:
        checked = subprocess.run([compiler, 'check', source], capture_output=True,
                                 text=True, timeout=30, check=False)
        assert checked.returncode == 0, checked.stdout + checked.stderr
        outputs.append(checked.stderr)
    for output in outputs:
        warnings = [line for line in output.splitlines() if "'s tick" in line and 'warning:' in line]
        if diagnostic:
            assert len(warnings) == 1 and diagnostic in warnings[0], output
        else:
            assert not warnings, output


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_netplay_restart(compiler, tmp_path, target, release):
    source = Path(__file__).resolve().parents[2] / 'core/tests/netplay_restart.dewy'
    binary = tmp_path / 'restart'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web rollback checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'restart.cjs'
        runner.write_text('const sloppyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [node, runner]
    for scenario in ['clean', 'late']:
        ran = subprocess.run([*command, scenario], capture_output=True, text=True,
                             timeout=15, check=False)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert not ran.stderr, ran.stderr
        values = list(map(int, ran.stdout.splitlines()))
        assert len(values) == 18, ran.stdout
        for start in range(0, 18, 6):
            left, right, left_state, right_state, left_desync, right_desync = values[start:start+6]
            assert 220 < left <= 240 and 220 < right <= 240, (scenario, start, values)
            assert left_state == 3 * (left - 2)
            assert right_state == 3 * (right - 2)
            assert left_desync == right_desync == -1


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.core_quick
def test_core_game_model(compiler, tmp_path, target, release):
    node = shutil.which('node')
    if target == 'wasm' and node is None:
        pytest.skip('Node is needed to execute the generated web runner')
    model = Path(__file__).resolve().parents[2] / 'examples/sloppy_core/paddle_model.dewy'
    shutil.copy2(model, tmp_path)
    source = tmp_path / 'model_test.dewy'
    source.write_text('''from p"paddle_model.dewy" import fresh, advance, Point
main=():>int64=>{
    let world=fresh()
    let original=world
    advance(@world 0.5 730.0)
    if world.position.x not=? 730.0 or world.position.y not=? 340.0 return 1
    if original.position.x not=? 640.0 or original.position.y not=? 220.0 return 2
    world.position=Point(730.0 610.0)
    world.velocity=Point(0.0 240.0)
    advance(@world 0.1 730.0)
    if world.score not=? 1 or world.velocity.y >=? 0.0 return 3
    world.position=Point(100.0 750.0)
    world.velocity=Point(0.0 240.0)
    advance(@world 0.1 730.0)
    if world.misses not=? 1 or world.position.y not=? 220.0 return 4
    advance(@world 0.0 0.0)
    if world.paddle not=? 80.0 return 5
    advance(@world 0.0 1280.0)
    if world.paddle not=? 1200.0 return 6
    return 42
}''')
    binary = tmp_path / 'model_test'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_numeric_matrix_range_reference(compiler, tmp_path, target, release):
    rng = random.Random(4187)
    cases = {}

    def array(values):
        return '[' + ' '.join(map(str, values)) + ']'

    for case in range(48):
        shape = [rng.randrange(5) for _ in range(1 + case % 4)]
        offsets, result_shape, declarations, selectors = [0], [], [], []
        for axis, size in enumerate(shape):
            if axis and size and rng.randrange(2):
                index = rng.randrange(size)
                selected = [index]
                selectors.append(str(index))
            else:
                first = rng.randrange(size) if size else 0
                step = rng.choice([-3, -2, -1, 1, 2, 3])
                available = len(range(first, size if step > 0 else -1, step)) if size else 0
                count = rng.randrange(available + 1)
                selected = [first + step * i for i in range(count)]
                expression = (f'[{first},{first + step}..{selected[-1]}]' if count else '[0..0)')
                declarations.append(f'let r{axis}={expression}')
                selectors.append(f'r{axis}')
                result_shape.append(count)
            offsets = [base * size + index for base in offsets for index in selected]
        original = [i * 7 - 3 for i in range(math.prod(shape))]
        picked = [original[i] for i in offsets]
        updated = original.copy()
        replacement = [1000 + i for i in range(len(offsets))]
        for index, value in zip(offsets, replacement, strict=True):
            updated[index] = value + 5
        selection = ' '.join(selectors)
        cases[f'matrix_{case}'] = (
            'main=()=>{\n'
            f'let values:array<int64>={array(original)}\n'
            f'let m=reshape(values {array(shape)}) let saved=m\n'
            + '\n'.join(declarations) + '\n'
            + f'let picked=m[{selection}]\n'
            + f'assert(picked.shape =? {array(result_shape)} and picked.data =? {array(picked)})\n'
            + f'm[{selection}]={array(replacement)}\nm[{selection}] .+= 5\n'
            + f'assert(m.data =? {array(updated)} and saved.data =? values)\nreturn 42\n}}')
    body = [f'assert(case_{i}() =? 42)' for i in range(len(cases))] + ['exit(42)']
    command, error = build_case_batch(compiler, tmp_path, cases, body, release, target)
    assert error is None, error
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_reaction_model(compiler, tmp_path, target, release):
    node = shutil.which('node')
    if target == 'wasm' and node is None:
        pytest.skip('Node is needed to execute the web simulation')
    model = Path(__file__).resolve().parents[2] / 'examples/sloppy_core/reaction_model.dewy'
    shutil.copy2(model, tmp_path)
    source = tmp_path / 'reaction_test.dewy'
    source.write_text('''from p"reaction_model.dewy" import fresh, paint, advance
simulate=()=>{
let field=fresh(8 6) let saved=field
paint(@field 4 3 1)
loop i in [0..8) advance(@field 0.035 0.062)
assert(saved.a.data =? fill(1.0 as float32 48) and saved.b.data =? fill(0.0 as float32 48))
assert(saved.steps =? 0)
let before=field paint(@field -100 -100 2) assert(field =? before)
return field
}
main=()=>{
let result=simulate() let before=alloc_count()
loop i in [0..20) {let trial=simulate() assert(trial.steps =? 8)}
assert(alloc_count() =? before)
printl(to_json(result))
return 42
}''')
    binary = tmp_path / 'reaction_test'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    actual = json.loads(ran.stdout)
    width, height = 8, 6
    a, b = [1.0] * (width * height), [0.0] * (width * height)
    for y in range(2, 5):
        for x in range(3, 6):
            a[y * width + x], b[y * width + x] = 0.5, 0.25
    for _ in range(8):
        next_a, next_b = a.copy(), b.copy()
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                i = y * width + x
                reaction = a[i] * b[i] * b[i]
                lap_a = a[i - width] + a[i + width] + a[i - 1] + a[i + 1] - 4 * a[i]
                lap_b = b[i - width] + b[i + width] + b[i - 1] + b[i + 1] - 4 * b[i]
                next_a[i] += 0.16 * lap_a - reaction + (1 - a[i]) * 0.035
                next_b[i] += 0.08 * lap_b + reaction - b[i] * (0.035 + 0.062)
        a, b = next_a, next_b
    assert actual['steps'] == 8
    assert actual['a']['shape'] == actual['b']['shape'] == [height, width]
    assert actual['a']['data'] == pytest.approx(a, rel=2e-6, abs=2e-6)
    assert actual['b']['data'] == pytest.approx(b, rel=2e-6, abs=2e-6)


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_forest_model(compiler, tmp_path, target, release):
    model = Path(__file__).resolve().parents[2] / 'examples/sloppy_core/forest_model.dewy'
    shutil.copy2(model, tmp_path)
    source = tmp_path / 'forest_test.dewy'
    source.write_text('''from p"forest_model.dewy" import fresh_forest, hill, ground_color
main=()=>{
    let forest=fresh_forest()
    if forest.trunks.length not=? 300 or forest.crowns.length not=? 300 return 1
    let original=forest
    forest.crowns[0].color.x=0.9
    if abs(original.crowns[0].color.x-0.2) >? 0.0001 return 2
    let repeated=fresh_forest()
    if abs(repeated.trunks[0].model[3].x-original.trunks[0].model[3].x) >? 0.0001 return 3
    loop tree in original.trunks {
        let position=tree.model[3]
        if abs(position.x) >? 55.0 or abs(position.z) >? 55.0 return 4
        if abs((position.y as float64)-hill(position.x as float64 position.z as float64)) >? 0.001 return 5
    }
    let empty=fresh_forest(0)
    if empty.trunks.length not=? 0 or hill(0.0 0.0) not=? 0.0 return 6
    let low=ground_color(0.0 (-10.0) 0.0)
    let high=ground_color(0.0 10.0 0.0)
    if abs(low.x-0.35) >? 0.0001 or abs(high.x-0.75) >? 0.0001 return 7
    return 42
}
''')
    binary = tmp_path / 'forest-model'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web forest checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'forest-model.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.fixture(scope='module')
def shader_driver():
    try:
        driver = ShaderDriver()
    except DriverUnavailable as error:
        pytest.skip(str(error))
    try:
        yield driver
    finally:
        driver.close()


@pytest.mark.parametrize('case', ['dunes', 'lit', 'parameter-copies'])
def test_core_shader_driver(compiler, shader_driver, tmp_path, case):
    if case == 'dunes':
        model = Path(__file__).resolve().parents[2] / 'examples/sloppy_core/dunes_model.dewy'
        shutil.copy2(model, tmp_path / model.name)
        body = 'from p"dunes_model.dewy" import sand_vs, sand_fs\n'
        pair = 'sand_vs sand_fs'
    elif case == 'lit':
        body = ''
        pair = 'lit_vs lit_fs'
    else:
        body = """Vertex:type=[pos:vec4 uv:vec2]
Surface:type=[tex:Texture tint:vec4]
Uniform:type=[surface:Surface]
Output:type=[pos:vec4 uv:vec2]
shift=(@p:vec2):>void=>{p.x+=1.0}
vertex=(v:Vertex u:Uniform):>Output=>{
let before=v.uv.x shift(@v.uv)
return Output(v.pos vec2(before v.uv.x))
}
fetch=(tex:Texture uv:vec2):>vec4=>sample(tex uv)
fragment=(i:Output u:Uniform):>vec4=>fetch(u.surface.tex i.uv)*u.surface.tint
"""
        pair = 'vertex fragment'
    body += f"""main=()=>{{let source=shader({pair})
write_file("shader.vert" source.vs); write_file("shader.frag" source.fs); return 0}}
"""
    source = tmp_path / 'shaders.dewy'
    source.write_text(body)
    binary = tmp_path / 'shaders'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], cwd=tmp_path, capture_output=True, text=True,
                         timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    shader_driver.validate((tmp_path / 'shader.vert').read_text(),
                           (tmp_path / 'shader.frag').read_text())


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_dunes_model(compiler, tmp_path, target, release):
    model = Path(__file__).resolve().parents[2] / 'examples/sloppy_core/dunes_model.dewy'
    shutil.copy2(model, tmp_path / model.name)
    source = tmp_path / 'dunes-model.dewy'
    source.write_text("""from p"dunes_model.dewy" import dune_height, robe_vertices, robe_indices, ribbon_vertices, ribbon_indices
main=()=>{
let cloth=robe_vertices(0.0 0.0) let indices=robe_indices()
if cloth.length not=? 175 or indices.length not=? 864 return 1
loop index in indices {if (index as int64) >=? cloth.length return 2}
loop v in cloth {if not is_finite(v.pos.x as float64) or abs(length(v.normal)-1.0) >? 0.0001 return 3}
let original=cloth cloth[0].pos.x+=10.0
if abs(cloth[0].pos.x-original[0].pos.x-10.0) >? 0.0001 return 4
let moving=robe_vertices(1.0 4.0)
if moving.length not=? cloth.length or moving[174].pos =? original[174].pos return 5
let points=[vec3(0 0 0) vec3(1 0 0) vec3(2 1 0) vec3(3 1 1)]
let ribbon=ribbon_vertices(points 0.2 0.0) let ribbon_ids=ribbon_indices(points.length)
if ribbon.length not=? 8 or ribbon_ids.length not=? 36 return 6
loop index in ribbon_ids {if (index as int64) >=? ribbon.length return 7}
if ribbon_vertices([] 0.2 0.0).length not=? 0 or ribbon_indices(0).length not=? 0 return 8
if dune_height(0.0 (-150.0)) <? 60.0 or dune_height(150.0 150.0) >? 60.0 return 9
return 42
}
""")
    binary = tmp_path / 'dunes-model'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web geometry checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'dunes.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('game', ['paddle', 'physics', 'forest', 'dunes', 'netpong', 'camera_roll', 'rollback_lab', 'outlines', 'controls', 'charts', 'reaction_field'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_game_web_build(compiler, tmp_path, game, release):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed to validate the web module')
    source = Path(__file__).resolve().parents[2] / f'examples/sloppy_core/{game}.dewy'
    output = tmp_path / game
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', 'wasm', '-o', output, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    html = output.with_suffix('.html').read_text()
    embedded = re.search(r'SLOPPY_WASM = "([A-Za-z0-9+/=]+)"', html)
    assert embedded, 'web host must include its compiled program'
    module = tmp_path / f'{game}.wasm'
    module.write_bytes(base64.b64decode(embedded[1], validate=True))
    validation = subprocess.run([node, '-e',
        "new WebAssembly.Module(require('fs').readFileSync(process.argv[1]));", module],
        capture_output=True, text=True, timeout=10, check=False)
    assert validation.returncode == 0, validation.stdout + validation.stderr


@pytest.mark.parametrize('game', ['paddle', 'physics', 'forest', 'dunes', 'netpong', 'camera_roll', 'rollback_lab', 'outlines', 'controls', 'charts', 'reaction_field'])
def test_core_game_renderer(compiler, tmp_path, game):
    source = Path(__file__).resolve().parents[2] / f'examples/sloppy_core/{game}.dewy'
    binary = tmp_path / game
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    screenshot = tmp_path / 'frame.png'
    env = {k: v for k, v in os.environ.items() if not k.startswith('SLOPPY_')}
    env.update(SLOPPY_SOFTWARE='1', SLOPPY_SCREENSHOT=str(screenshot), SLOPPY_FRAMES='3',
               SLOPPY_WINDOW='1280x720', SLOPPY_INPUT='1:mouse=800x620,2:mouse_right+,3:b+')
    ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=15, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    data = screenshot.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', data[16:24]) == (1280, 720)
    if game == 'reaction_field':
        from PIL import Image
        with Image.open(screenshot) as frame:
            pixels = frame.crop((40, 152, 790, 646)).convert('RGB').tobytes()
        warm = sum(red > 100 and red > green > blue
                   for red, green, blue in zip(pixels[0::3], pixels[1::3], pixels[2::3]))
        assert warm > 1000, 'the field must contain visible reaction patterns'


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_software_raster_chunks(compiler, tmp_path, release):
    source = Path(__file__).resolve().parents[2] / 'core/tests/software_raster.jo'
    binary = tmp_path / 'raster'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    for threads in [1, 2]:
        env = {k: v for k, v in os.environ.items() if not k.startswith('SLOPPY_')}
        env.update(SLOPPY_THREADS=str(threads), SLOPPY_SOFT_SCALE='0.5')
        ran = subprocess.run([binary], env=env, capture_output=True, text=True,
                             timeout=10, check=False)
        assert ran.returncode == 42, (threads, ran.stdout, ran.stderr)


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_chart_render(compiler, tmp_path, release):
    source = Path(__file__).resolve().parents[2] / 'core/tests/chart_render.dewy'
    binary = tmp_path / 'chart'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    env = {k: v for k, v in os.environ.items() if not k.startswith('SLOPPY_')}
    env['SLOPPY_SOFTWARE'] = '1'
    ran = subprocess.run([binary], cwd=tmp_path, env=env, capture_output=True,
                         text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    data = (tmp_path / 'chart.png').read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', data[16:24]) == (320, 240)


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_slider_controls(compiler, tmp_path, release):
    source = Path(__file__).resolve().parents[2] / 'core/tests/slider_controls.dewy'
    binary = tmp_path / 'sliders'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    scripts = {
        'drag': ('1:mouse=405x80,1:mouse_left+,2:mouse=600x350,3:mouse=200x210,4:mouse_left-,'
                 '5:mouse=40x220,5:mouse_left+,6:mouse=600x80,7:mouse_left-,'
                 '8:mouse=180x220,8:mouse_left+,9:mouse=210x450,10:mouse_left-'),
        'keys': '1:right+,2:right-,3:right+,4:right-',
        'touch': '1:touch1=405x80,2:touch1=600x350,3:touch1-',
        'click': ('1:mouse=405x80,1:mouse_left+,1:mouse_left-,'
                  '2:mouse=320x220,2:mouse_left+,2:mouse_left-,3:mouse=40x220,'
                  '4:mouse=330x80,4:mouse_left+,4:mouse_left-'),
        'descending': '1:mouse=360x220,1:mouse_left+,2:mouse=700x450,3:mouse_left-',
    }
    for scenario, script in scripts.items():
        env = {k: v for k, v in os.environ.items() if not k.startswith('SLOPPY_')}
        env.update(SLOPPY_SOFTWARE='1', SLOPPY_SCREENSHOT=str(tmp_path / f'{scenario}.png'),
                   SLOPPY_FRAMES='10', SLOPPY_WINDOW='640x480', SLOPPY_INPUT=script)
        ran = subprocess.run([binary], env=env, capture_output=True, text=True,
                             timeout=15, check=False)
        assert ran.returncode == 0, (scenario, ran.stdout, ran.stderr)
        values = [list(map(float, line.split())) for line in ran.stdout.splitlines()]
        assert [row[0] for row in values] == list(range(11)), ran.stdout
        if scenario == 'drag':
            assert [row[1] for row in values] == [10, 20, 30, 10, 10, 10, 10, 10, 10, 10, 10]
            assert [row[2] for row in values] == [0, 0, 0, 0, 0, -5, 5, 5, 0, 1, 1]
            assert all(row[3] == 0 for row in values)
        elif scenario == 'keys':
            assert [row[1] for row in values] == [10, 12.5, 12.5, 15, 15, 15, 15, 15, 15, 15, 15]
            assert all(row[2:] == [0, 0] for row in values)
        elif scenario == 'touch':
            assert [row[1] for row in values] == [10, 20, 30, 30, 30, 30, 30, 30, 30, 30, 30]
            assert all(row[2:] == [0, 0] for row in values)
        elif scenario == 'click':
            assert [row[1] for row in values] == [10, 20, 20, 20, 10, 10, 10, 10, 10, 10, 10]
            assert [row[2] for row in values] == [0, 0, 5, 5, 5, 5, 5, 5, 5, 5, 5]
            assert all(row[3] == 0 for row in values)
        else:
            assert [row[3] for row in values] == [0, 10, -10, -10, -10, -10, -10, -10, -10, -10, -10]
            assert all(row[1:3] == [10, 0] for row in values)


@pytest.mark.core_quick
def test_core_check_and_format_boundary(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    text = 'unused=()=>missing\nmain=()=>42'
    source.write_text(text)
    checked = subprocess.run([compiler, 'check', source], capture_output=True,
                             text=True, timeout=10, check=False)
    assert checked.returncode != 0 and 'unknown' in checked.stderr, checked.stdout + checked.stderr
    formatted = subprocess.run([compiler, 'fmt', source], capture_output=True,
                               text=True, timeout=10, check=False)
    assert formatted.returncode == 0, formatted.stdout + formatted.stderr
    assert source.read_text() == 'unused = () => missing\nmain = () => 42\n'


@pytest.mark.parametrize(('text', 'expected', 'errors'), [
    (('1+2\nlet xs=[20 22]\nlet saved=xs\nxs[0]=99\nsaved[0]+saved[1]\n'
     'Point:type=[x:int64 y:int64]\nlet point=Point[20 22]\npoint.x=40\npoint.x+point.y\n'
     '1/2+1/3\n:type 1/2\n'), ['3', '42', '62', '5/6', 'Rational'], []),
    (('let score=20\nread=()=>score\nscore=40\nread()+2\nlet score=99\nread()\nscore\n'
     'identity=<T>(value:T):>T=>value\nidentity(42)\n'), ['42', '40', '99', '42'], []),
    ('repl_add=(x:int64 y:int64):>int64=>x+y\n:type repl_add\n:type [1 2]\n:type 40+2\n',
     ['repl_add = (x: int64 y: int64):>int64', 'array<int64>', 'int64'], []),
    (('{\n# A comment inside the final expression.\nlet x=20\nx+22\n}\n'
     'f=(x)=>{\nx+2\n}\nf(40)\n[loop i in [0..3) i*2]\n'
     'let text="""first\nan unmatched " inside triple quotes\nlast"""\ntext.length >? 10\n'
     'let raw=r"\\hello"\nraw.length\n'), ['42', '42', '[0, 2, 4]', 'true', '6'], []),
    (('let xs=[20 22]\n{xs[0]=99 panic("restore values")}\nxs[0]\n'
     'missing_repl_name\nxs[1]\nbroken=()=>missing_repl_name\n'
     'explode=():>int64=>{panic("restore declarations") return 42}\n'
     'let transient_repl=explode()\ntransient_repl\nlet transient_repl=42\ntransient_repl\n'),
     ['20', '22', '42'], ['panic: restore values', "unknown name 'missing_repl_name'",
                         'panic: restore declarations', "unknown name 'transient_repl'"]),
    ('let calls=0\nnext=()=>{calls+=1 return 42}\n:type next()\ncalls\nnext()\ncalls\n',
     ['int64', '0', '42', '1'], []),
    (('let calls=0\nnext=()=>{calls+=1 return [20 22]}\nconst saved=next()\n'
     'saved\nsaved\ncalls\nsaved[0]=99\nsaved\nlet saved=[42]\nsaved\n'),
     ['[20, 22]', '[20, 22]', '1', '[20, 22]', '[42]'], ['cannot modify const']),
], ids=['values', 'bindings', 'types', 'multiline', 'recovery', 'query-effects', 'constant-values'])
def test_core_repl_inputs(compiler, tmp_path, text, expected, errors):
    env = {**os.environ, 'TMPDIR': str(tmp_path)}
    ran = subprocess.run([compiler, 'repl'], input=text + ':quit\n', cwd=tmp_path,
                         env=env, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == expected, ran.stdout + ran.stderr
    if errors:
        for message in errors:
            assert message in ran.stderr, ran.stderr
    else:
        assert not ran.stderr, ran.stderr
    assert not list((tmp_path / 'dewy-repl').glob('*.bin'))


def test_core_repl_imports(compiler, tmp_path):
    (tmp_path / 'seed.dewy').write_text('printl"seed"\nlet offset=2\n')
    (tmp_path / 'helper.dewy').write_text('from seed import offset\nprintl"helper"\n'
                                         'twice=(x)=>x*2+offset\n')
    (tmp_path / 'helper.jo').write_text('twice = (x: int) -> int: 0\n')
    text = ('import helper as h\nh.twice(20)\nfrom helper import twice\ntwice(20)\n'
            'import p"helper.dewy" as again\nagain.twice(20)\n:quit\n')
    ran = subprocess.run([compiler, 'repl'], input=text, cwd=tmp_path,
                         env={**os.environ, 'TMPDIR': str(tmp_path)}, capture_output=True,
                         text=True, timeout=20, check=False)
    assert ran.returncode == 0 and not ran.stderr, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['seed', 'helper', '42', '42', '42']



def test_core_repl_failed_import(compiler, tmp_path):
    (tmp_path / 'gate.dewy').write_text('if not file_exists("ready") panic("retry import")\n'
                                       'let answer=42\n')
    text = ('import gate as g\ng.answer\nwrite_file("ready" "yes")\n'
            'import gate as g\ng.answer\n:quit\n')
    ran = subprocess.run([compiler, 'repl'], input=text, cwd=tmp_path,
                         env={**os.environ, 'TMPDIR': str(tmp_path)}, capture_output=True,
                         text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['true', '42'], ran.stdout + ran.stderr
    assert 'panic: retry import' in ran.stderr
    assert "unknown name 'g'" in ran.stderr


def test_core_repl_help_and_eof(compiler, tmp_path):
    ran = subprocess.run([compiler, 'repl'], input=':help\n40+2\n', cwd=tmp_path,
                         env={**os.environ, 'TMPDIR': str(tmp_path)}, capture_output=True,
                         text=True, timeout=20, check=False)
    assert ran.returncode == 0 and not ran.stderr, ran.stdout + ran.stderr
    assert 'Type Dewy' in ran.stdout and 'Sloppy' not in ran.stdout
    assert ran.stdout.endswith('42\n')


def test_core_repl_terminal(compiler, tmp_path):
    import pty
    import select
    import signal
    import time

    master, slave = pty.openpty()
    env = {**os.environ, 'TMPDIR': str(tmp_path),
           'DEWY_REPL_HISTORY': str(tmp_path / 'history')}
    process = subprocess.Popen([compiler, 'repl'], cwd=tmp_path, env=env,
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = bytearray()
    position = 0

    def expect(needle):
        nonlocal position
        deadline = time.monotonic() + 10
        while True:
            found = output.find(needle, position)
            if found >= 0:
                position = found + len(needle)
                return
            remaining = deadline - time.monotonic()
            assert remaining > 0, bytes(output)
            ready, _, _ = select.select([master], [], [], remaining)
            assert ready, bytes(output)
            output.extend(os.read(master, 16384))

    try:
        expect(b'Dewy (:help')
        expect(b'>>> ')
        os.write(master, b'let repl_unique=40\nrepl_uni\t+2\n')
        expect(b'\r\n42\r\n')
        # Cancel an unfinished input, then recall the preceding complete line.
        os.write(master, b'bad_partial\x03\x1b[A\n')
        expect(b'\r\n42\r\n')
        os.write(master, b'{repl_unique=99 printl"running" loop true {}}\n')
        expect(b'\r\nrunning\r\n')
        os.killpg(process.pid, signal.SIGINT)
        expect(b'interrupted; the session is as it was before this input')
        os.write(master, b'repl_unique+2\n')
        expect(b'\r\n42\r\n')
        expect(b'>>> ')
        os.write(master, b'\x04')
        assert process.wait(timeout=5) == 0, bytes(output)
        assert 'repl_unique+2' in (tmp_path / 'history').read_text()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        os.close(master)


@pytest.mark.parametrize('command', ['update', 'upgrade', 'add'])
def test_core_unavailable_cli(compiler, tmp_path, command):
    result = subprocess.run([compiler, command], cwd=tmp_path, capture_output=True,
                            text=True, timeout=5, check=False)
    assert result.returncode == 2
    assert 'dewy-core:' in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.core_quick
def test_core_cli_identity(compiler):
    result = subprocess.run([compiler, '--version'], capture_output=True, text=True,
                            timeout=5, check=False)
    assert result.returncode == 0 and result.stdout.startswith('dewy-core ')
    result = subprocess.run([compiler, '--help'], capture_output=True, text=True,
                            timeout=5, check=False)
    assert result.returncode == 0 and 'file.dewy' in result.stderr


@pytest.mark.parametrize('kind', ['game', 'arcade', 'platformer', '3d', 'story', 'online', 'program'])
def test_core_new_project(compiler, tmp_path, kind):
    project = tmp_path / 'project with spaces'
    made = subprocess.run([compiler, 'new', project, kind], capture_output=True,
                          text=True, timeout=5, check=False)
    assert made.returncode == 0, made.stdout + made.stderr
    source = project / ('project-with-spaces.dewy' if kind in {'online', 'arcade', 'story'} else 'main.dewy')
    assert source.is_file() and (project / 'README.md').is_file()
    assert not list(project.glob('*.jo'))
    binary = project / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_SOFTWARE='1', SLOPPY_THREADS='2', SLOPPY_FRAMES='3',
               SLOPPY_SCREENSHOT=str(project / 'frame.png'), SLOPPY_SAVE_DIR=str(project / 'saves'))
    ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    if kind == 'program':
        assert ran.stdout == 'Hello, Dewy!\n'
    else:
        assert (project / 'frame.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
        built = subprocess.run([compiler, 'build', source, '--target', 'wasm', '-o', binary],
                               capture_output=True, text=True, timeout=30, check=False)
        assert built.returncode == 0, built.stdout + built.stderr
        assert (project / 'main.html').is_file()
        if kind == 'online':
            assert 'distinct .dewy source filename' in built.stderr
            assert '`build:`' not in built.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_platformer_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[2] / 'core/lib/new/dewy/platformer.dewy'
    model = template.read_text().split('# Presentation and live game state.', 1)[0]
    body = model + r'''
main=()=>{
    let map=make_level("........\n........\n........\n........\n########")
    let at=vec2(72 168)
    let p=spawn(at)
    loop i in [0..60) p=tick(p map at Pad[] 1.0/120.0).player
    if not p.on_ground or abs(p.box.y-152.0)>?0.001 or p.vel.y not=?0.0 return 1
    let saved=p
    let jumping=tick(p map at Pad[pressed=true held=true] 1.0/120.0)
    if not jumping.jumped or jumping.player.box.y>=?p.box.y or p not=?saved return 2
    p=jumping.player
    loop i in [0..14) p=tick(p map at Pad[held=true] 1.0/120.0).player
    if tick(p map at Pad[pressed=true held=true] 1.0/120.0).jumped return 3
    let held=tick(p map at Pad[held=true] 1.0/120.0).player
    let released=tick(p map at Pad[] 1.0/120.0).player
    if released.vel.y<=?held.vel.y or released.box.y<=?held.box.y return 4

    # A recent ledge departure permits one jump; an expired window does not.
    let ledge=spawn(vec2(500 100))
    ledge.coyote=0.05
    if not tick(ledge map at Pad[pressed=true held=true] 0.01).jumped return 5
    ledge.coyote=0.0
    if tick(ledge map at Pad[pressed=true held=true] 0.01).jumped return 6

    # Press just before landing: consume the buffered jump on the next step.
    let falling=spawn(vec2(72 170))
    falling.vel.y=600.0
    let landed=tick(falling map at Pad[pressed=true held=true] 0.01)
    if not landed.player.on_ground or landed.jumped or landed.impact<?600.0 return 7
    if not tick(landed.player map at Pad[held=true] 0.01).jumped return 8

    let platforms=make_level("........\n........\n========\n........\n########")
    let standing=spawn(vec2(72 76))
    standing.on_ground=true
    let stay=tick(standing platforms at Pad[] 0.01).player
    let drop=tick(standing platforms at Pad[drop=true] 0.01).player
    if not stay.on_ground or drop.on_ground or drop.box.y<=?stay.box.y return 9
    let rising=spawn(vec2(72 120))
    rising.vel.y=-600.0
    let through=tick(rising platforms at Pad[held=true] 0.01).player
    if through.box.y>=?96.0 or through.vel.y>=?0.0 return 10

    let slopes=make_level(r"/\")
    let up=tilemap_move(slopes 0 Rect(10 -60 28 40) vec2(0 100))
    let down=tilemap_move(slopes 0 Rect(58 -60 28 40) vec2(0 100))
    if not up.hit_y or not down.hit_y or abs(up.rect.y+16.0)>?0.001 or abs(down.rect.y+16.0)>?0.001 return 11
    let wall=make_level("..#\n..#\n..#")
    let stopped=tilemap_move(wall 0 Rect(20 20 28 40) vec2(100 0))
    if not stopped.hit_x or stopped.rect.x not=?68.0 return 12

    let lost=spawn(vec2(500 900))
    lost.vel=vec2(50 600)
    if tick(lost map at Pad[] 0.01).player not=?spawn(at) return 13
    let moving=tick(saved map at Pad[move=-1.0] 0.01).player
    if moving.facing not=?-1.0 or moving.vel.x>=?0.0 return 14

    let coins=[Coin[pos=vec2(72 100)] Coin[pos=vec2(150 100)]]
    let original=coins
    if collect(@coins vec2(72 100) 0.01) not=?1 return 15
    if collect(@coins vec2(72 100) 0.01) not=?0 return 16
    if not coins[0].taken or coins[1].taken or original[0].taken return 17
    if coins[0].pop.t<=?0.0 or original[0].pop.t not=?0.0 return 18
    if markers("o").length not=?16 or markers("@")[0] not=?vec2(72 600) return 19
    return 42
}
'''
    result, output = run_value_batch(compiler, tmp_path, {'platformer-model': body}, release, target)['platformer-model']
    assert result == '42', output


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_3d_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[2] / 'core/lib/new/dewy/3d.dewy'
    model = template.read_text().split('# Presentation and live game state.', 1)[0]
    body = model + r'''
main=()=>{
    let forward=view_direction(0.0 0.0)
    if length(forward-vec3(0 0 -1))>?0.00001 return 1
    if length(view_direction(PI/2.0 0.0)-vec3(-1 0 0))>?0.00001 return 2
    if abs(length(view_direction(0.7 0.4))-1.0)>?0.00001 return 3
    let origin=vec3(0 0 0)
    let targets=[Orb[pos=vec3(0 0 -8)] Orb[pos=vec3(0 0 -4)] Orb[pos=vec3(0 0 4)]]
    let saved=targets
    if shot_target(targets origin forward 0.0 100.0) not=?1 return 4
    if shot_target(targets origin forward 0.0 3.0) not=?-1 return 5
    if shot_target(targets origin forward 0.0 3.75) not=?1 return 6
    targets[1].pop=0.1
    if shot_target(targets origin forward 0.0 100.0) not=?0 or saved[1].pop not=?0.0 return 7
    if shot_target([Orb[pos=vec3(1 0 -4)]] origin forward 0.0 100.0) not=?-1 return 8
    if shot_target([Orb[pos=vec3(0 0 4)]] origin forward 0.0 100.0) not=?-1 return 9
    if shot_target([Orb[pos=origin]] origin forward 0.0 100.0) not=?0 return 10
    if shot_target([] origin forward 0.0 100.0) not=?-1 return 11
    if abs(orb_at(Orb[pos=origin] PI/4.0).y-0.25)>?0.00001 return 12

    # The same World/Character calls used by the game, with an independent saved world.
    let w=physics3d.World[gravity=vec3(0 -GRAVITY 0)]
    w.add_box(vec3(0 -0.5 0) vec3(40 1 40) kind=physics3d.BodyKind.fixed)
    let wall=w.add_box(vec3(0 2 -4) vec3(10 4 1) kind=physics3d.BodyKind.fixed)
    let body=w.add_box(vec3(5 1 0) vec3(2 2 2) density=150)
    let before=w
    let actor=w.character(vec3(0 0 0) radius=0.35)
    loop i in [0..10) w.walk(@actor vec3(0 0 0) 1.0/120.0)
    if not actor.on_ground or abs(actor.feet.y)>?0.01 return 13
    w.walk(@actor vec3(0 0 0) 1.0/120.0 jump=JUMP)
    if actor.feet.y<=?0.0 or actor.on_ground return 14
    loop i in [0..180) w.walk(@actor vec3(0 0 -WALK) 1.0/120.0)
    if actor.feet.z<?-3.2 or actor.feet.z>?-3.0 or not actor.on_ground return 15
    let hit=w.raycast(vec3(0 1 0) vec3(0 1 -10))
    let distance=match hit {h:physics3d.Hit=>float64(h.fraction)*10.0 <none>=>100.0}
    if abs(distance-3.5)>?0.001 return 16
    if shot_target(targets vec3(0 1 0) forward 0.0 distance) not=?-1 return 17
    w.push(body vec3(400 0 0) vec3(5 1 0))
    w.step(1.0/60.0)
    if w.pos(body).x<=?5.0 or before.pos(body).x not=?5.0 or before.velocity(body) not=?vec3(0 0 0) return 18
    w.remove(body)
    if w.alive(body) or not before.alive(body) return 19
    if not w.alive(wall) return 20
    return 42
}
'''
    result, output = run_value_batch(compiler, tmp_path, {'3d-model': body}, release, target)['3d-model']
    assert result == '42', output


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_arcade_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[2] / 'core/lib/new/dewy/arcade.dewy'
    model = template.read_text().split('# Presentation and live game state.', 1)[0]
    body = model + r'''
main=()=>{
    let game=fresh(42)
    let saved=game
    if length(game.gold-game.player)<=?260.0 return 1
    game.rock_wait=0.0
    let replay=game
    advance(@game vec2(1 0) 1.0/60.0)
    advance(@replay vec2(1 0) 1.0/60.0)
    if game not=?replay or game.rocks.length not=?1 return 2
    if saved.rocks.length not=?0 or saved.elapsed not=?0.0 return 3
    if game.player.x<=?640.0 or game.vel.x<=?0.0 return 4
    game.player=vec2(1263 703)
    game.vel=vec2(420 420)
    advance(@game vec2(1 1) 0.1)
    if game.player not=?vec2(1264 704) return 5

    let collecting=fresh(7)
    collecting.player=collecting.gold
    let before=collecting
    advance(@collecting vec2(0 0) 0.01)
    if collecting.score not=?1 or before.score not=?0 return 6
    if length(collecting.gold-collecting.player)<=?260.0 return 7

    let moving=fresh(19)
    moving.rocks=[Rock[pos=vec2(200 200) vel=vec2(30 -20) r=20 spin=2.0]
                  Rock[pos=vec2(1500 200) vel=vec2(30 0) r=20]]
    let old=moving
    advance(@moving vec2(0 0) 0.1)
    if moving.rocks.length not=?1 or moving.rocks[0].pos not=?vec2(203 198) return 8
    if abs(moving.rocks[0].angle-0.2)>?0.00001 or old.rocks[0].angle not=?0.0 or old.rocks.length not=?2 return 9
    moving.rocks=[Rock[pos=moving.player vel=vec2(0 0) r=20]]
    advance(@moving vec2(0 0) 0.01)
    if not moving.over return 10
    let crashed=moving
    advance(@moving vec2(1 1) 1.0)
    if moving not=?crashed return 11

    let late=fresh(23)
    late.elapsed=1000.0
    late.rock_wait=0.0
    advance(@late vec2(0 0) 0.01)
    if late.rock_wait not=?ROCK_GAP_MIN or length(late.rocks[0].vel)>?ROCK_SPEED_MAX*1.2+0.001 return 12
    loop seed in [0..64) {
        let trial=fresh(seed)
        if trial.gold.x<?80 or trial.gold.x>=?1200 or trial.gold.y<?100 or trial.gold.y>=?660 return 13
        let same=trial
        loop frame in [0..180) {
            let input=vec2(sin(float64(frame)*0.1) cos(float64(frame)*0.1))
            advance(@trial input 1.0/60.0)
            advance(@same input 1.0/60.0)
        }
        if trial not=?same return 14
    }
    return 42
}
'''
    result, output = run_value_batch(compiler, tmp_path, {'arcade-model': body}, release, target)['arcade-model']
    assert result == '42', output


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_story_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[2] / 'core/lib/new/dewy/story.dewy'
    model = template.read_text().split('# Presentation and live game state.', 1)[0]
    body = model + r'''
main=()=>{
    loop option in [0..2) {
        let reading=fresh()
        if reading.step.text not=?"The bell rang twice across the empty square." return 1
        let menus=0
        let ending=false
        loop i in [0..20) {
            let restored=resume(reading.bookmark)
            if restored.step not=?reading.step or restored.background not=?reading.background or restored.shown not=?reading.shown return 2
            if restored.script.vars not=?reading.script.vars return 3
            let saved=to_text(reading.bookmark)
            let decoded=from_text<Bookmark>(saved)
            match decoded {
                bookmark:Bookmark=>{
                    let loaded=resume(bookmark)
                    if loaded.step not=?reading.step or loaded.shown not=?reading.shown or loaded.background not=?reading.background return 4
                }
                error:TextError=>{printl(error.message); return 5}
            }
            if reading.step.kind=?StoryKind.end {ending=true; break}
            if reading.step.kind=?StoryKind.choice {
                menus+=1
                if reading.shown.length not=?2 or reading.step.choices.length not=?2 return 6
                let snapshot=reading
                choose(@reading -1)
                choose(@reading 99)
                if reading not=?snapshot return 7
                choose(@reading option)
                if snapshot.script.vars.length not=?0 return 8
                if option=?0 and reading.step.speaker not=?"Mira" return 9
                if option=?1 and reading.step.speaker not=?"Ren" return 10
            } else advance(@reading)
        }
        if not ending or menus not=?1 or reading.shown.length not=?0 return 11
        if reading.background not=?SCENES["tower"] return 12
        if option=?0 and reading.script.vars.get("mira")??0 not=?1 return 13
        if option=?1 and reading.script.vars.get("ren")??0 not=?1 return 14
        let restarted=fresh()
        if restarted.step.text not=?"The bell rang twice across the empty square." or restarted.script.vars.length not=?0 return 15
    }
    return 42
}
'''
    result, output = run_value_batch(compiler, tmp_path, {'story-model': body}, release, target)['story-model']
    assert result == '42', output


@pytest.mark.parametrize('flags', [[], ['--release']])
@pytest.mark.parametrize(('kind', 'count'), [('platformer', 2), ('3d', 1), ('arcade', 2), ('story', 2)])
def test_core_game_starter_tests(compiler, tmp_path, flags, kind, count):
    template = Path(__file__).resolve().parents[2] / f'core/lib/new/dewy/{kind}.dewy'
    env = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'SLOPPY_THREADS': '2',
           'SLOPPY_SAVE_DIR': str(tmp_path / 'saves')}
    result = subprocess.run([compiler, 'test', *flags, template], env=env, capture_output=True,
                            text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'{count} test' in result.stdout



@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_online_starter_model(compiler, tmp_path, target, release):
    template = Path(__file__).resolve().parents[2] / 'core/lib/new/dewy/online.dewy'
    model = template.read_text().split('# Connection and presentation state', 1)[0]
    body = model + """
main=()=>{
    let original=Game[]
    let moving=tick(original [Pad[x=1 y=-1] Pad[x=-1 y=1]])
    if moving.players[0].pos not=?vec2(406 354) or moving.players[1].pos not=?vec2(874 366) return 1
    if original.players[0].pos not=?vec2(400 360) return 2
    let edge=Game[]
    edge.players[0].pos=vec2(1259 21)
    let clamped=tick(edge [Pad[x=1 y=-1] Pad[]])
    if clamped.players[0].pos not=?vec2(1260 20) return 3
    let state=Game[]
    loop i in [0..WIN) {
        state.players[0].pos=state.coin
        let saved=state
        let next=tick(state [Pad[] Pad[]])
        if next not=?tick(state [Pad[] Pad[]]) return 4
        if state not=?saved or next.players[0].score not=?i+1 return 5
        state=next
    }
    if state.winner not=?0 or state.taken not=?WIN return 6
    if tick(state [Pad[x=1] Pad[y=1]]) not=?state return 7
    return 42
}
"""
    result, output = run_value_batch(compiler, tmp_path, {'online-model': body}, release, target)['online-model']
    assert result == '42', output


@pytest.mark.parametrize('directory, entry', [('Coin Race!', 'coin-race.dewy'),
                                             ('___', '___.dewy'), ('!!!', 'online.dewy')])
@pytest.mark.parametrize('kind', ['online', 'arcade', 'story'])
def test_core_named_starter_filename(compiler, tmp_path, directory, entry, kind):
    if directory == '!!!':
        entry = f'{kind}.dewy'
    project = tmp_path / directory
    made = subprocess.run([compiler, 'new', str(project) + '/', kind],
                          capture_output=True, text=True, timeout=5, check=False)
    assert made.returncode == 0, made.stdout + made.stderr
    assert (project / entry).is_file()
    assert f'dewy-core watch {entry}' in (project / 'README.md').read_text()


@pytest.mark.parametrize('flags', [[], ['--release']])
def test_core_arcade_starter_saved_score(compiler, tmp_path, flags):
    template = Path(__file__).resolve().parents[2] / 'core/lib/new/dewy/arcade.dewy'
    source = tmp_path / 'score-test.dewy'
    source.write_text(template.read_text() + '''
test "save round" {
    best=0
    game.score=7
    crash()
    assert(best=?7 and screen=?Screen.over and load_data("best")??""=?"7")
    game.score=3
    crash()
    assert(best=?7 and load_data("best")??""=?"7")
    start()
    assert(screen=?Screen.playing and game.score=?0 and not game.over and best=?7)
}
test "load round" {assert(best=?7)}
''')
    env = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'SLOPPY_THREADS': '2',
           'SLOPPY_SAVE_DIR': str(tmp_path / 'saves')}
    for name in ['save round', 'load round']:
        result = subprocess.run([compiler, 'test', *flags, source, name], env=env,
                                capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert '1 test passed' in result.stdout


@pytest.mark.parametrize('flags', [[], ['--release']])
def test_core_story_starter_saved_reading(compiler, tmp_path, flags):
    template = Path(__file__).resolve().parents[2] / 'core/lib/new/dewy/story.dewy'
    source = tmp_path / 'reading-test.dewy'
    source.write_text(template.read_text() + '''
test "save reading" {
    reading=fresh()
    advance(@reading)
    assert(reading.step.speaker=?"Mira" and reading.shown["mira"]=?"left")
    on_quit()
}
test "load reading" {
    assert(reading.step.speaker=?"Mira" and reading.step.text=?"You came! I wasn't sure you would.")
    assert(reading.shown["mira"]=?"left" and reading.background=?SCENES["square"])
}
''')
    env = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'SLOPPY_THREADS': '2',
           'SLOPPY_SAVE_DIR': str(tmp_path / 'saves')}
    for name in ['save reading', 'load reading']:
        result = subprocess.run([compiler, 'test', *flags, source, name], env=env,
                                capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert '1 test passed' in result.stdout


def test_core_new_existing_directory(compiler, tmp_path):
    marker = tmp_path / 'main.dewy'
    marker.write_text('existing work')
    made = subprocess.run([compiler, 'new', tmp_path], capture_output=True,
                          text=True, timeout=5, check=False)
    assert made.returncode != 0 and 'already exists' in made.stderr
    assert marker.read_text() == 'existing work'
    assert list(tmp_path.iterdir()) == [marker]


def test_core_new_unknown_template(compiler, tmp_path):
    project = tmp_path / 'project'
    made = subprocess.run([compiler, 'new', project, 'unknown'], capture_output=True,
                          text=True, timeout=5, check=False)
    assert made.returncode != 0 and 'no template' in made.stderr
    assert not project.exists()


@pytest.mark.parametrize('name', quick_parameters([*[name for name in CASES if name.startswith(('closure-', 'game-camera-', 'game-polyline-', 'game-shadow-', 'game-font-', 'game-chart-', 'constant-', 'format-', 'set-', 'json-', 'sort-', 'spread-', 'end-index-', 'numeric-', 'sequence-', 'slice-update-', 'range-index-', 'coalesce-', 'compound-', 'loop-else-', 'loop-label-', 'stored-range-', 'dictionary-', 'array-comparison-', 'fixed-array-', 'unit-range-', 'stepped-range-', 'optimizer-', 'power-', 'rational-', 'bigint-', 'overload-group-', 'generic-', 'match-', 'named-', 'argument-', 'conversion-', 'record-', 'default-reference-', 'comprehension-', 'unpack-'))], 'floor-literal-inference', 'unsigned-constant-math', 'narrow-integers', 'scientific', 'optional-managed-copy', 'optional-union', 'array-slices', 'slice-bound-side-effect', 'slice-replaced-source', 'grapheme-length', 'grapheme-index', 'grapheme-slices', 'grapheme-loop', 'grapheme-zipped-loop', 'grapheme-bound-side-effect', 'panic-ended-search', 'binary-literals', 'utf8-decode', 'utf8-copy'], QUICK_CASES))
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_value_web(value_batches, name, release):
    code, output = value_batches(name, release, 'wasm')
    assert code == '42', f'{name}: {code}\n{output}'



def test_core_x64_compare_branch_layout(compiler, tmp_path):
    objdump = shutil.which('objdump')
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64') or not objdump:
        pytest.skip('requires an x86-64 Linux host and objdump')
    cutoffs = [-129, -128, 0, 1, 127, 128, 65536, *[i * 13 + 3 for i in range(24)]]
    body = '\n'.join(f'if x <? {cutoff} printl({i})' for i, cutoff in enumerate(cutoffs))
    source = tmp_path / 'branches.dewy'
    source.write_text('branch_probe=(x:int64 y:int64):>void=>{\n'
                      'if x <? y printl(777)\n' + body +
                      '\n}\nmain=()=>{branch_probe(100 200) return 42}\n')
    binary = tmp_path / 'branches'
    built = subprocess.run([compiler, 'build', source, '--release', '-o', binary],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['777', *[str(i) for i, cutoff in enumerate(cutoffs) if 100 < cutoff]]
    dumped = subprocess.run([objdump, '-d', '--disassemble=branch_probe', binary],
                            capture_output=True, text=True, timeout=10, check=True)
    instructions = []
    for line in dumped.stdout.splitlines():
        match = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)\s*(\S+)', line)
        if match:
            instructions.append((int(match[1], 16), len(match[2].split()), match[3]))
    pairs = [(left, right) for left, right in zip(instructions, instructions[1:])
             if left[2].startswith('cmp') and right[2].startswith('j') and right[2] != 'jmp']
    assert len(pairs) >= 8, dumped.stdout
    for compare, branch in pairs:
        # The fused pair must neither cross nor end on the 32-byte boundary.
        assert compare[0] // 32 == (branch[0] + branch[1]) // 32, dumped.stdout


@pytest.mark.parametrize('body', [
    'let xs=[20 22] let out:array<int64>=[] let start=0-args().length out.extend(xs[start..1))',
    'let xs=[20 22] let out:array<int64>=[] out.extend(xs[0..3))',
    'let xs=[20 22] let out:array<int64>=[] out.extend(xs[2..1))',
    ('let xs:array<int64 length=2>=[20 22] let out:array<array<int64>>=[[]] '
     'choose=():>int64=>{panic("destination evaluated before invalid slice") return 0} '
     'out[choose()].extend(xs[0..3))'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_extend_slice_errors(error_batches, body, target, release):
    ran = error_batches('bounds', body, release, target)
    output = ran.stdout + ran.stderr
    assert ran.returncode != 0 and 'slice' in output, output
    assert 'destination evaluated before invalid slice' not in output, output


def test_core_slice_bounds_panic(compiler, tmp_path):
    source = tmp_path / 'bounds.dewy'
    source.write_text('stop=()=>9\nmain=()=>{let xs=[20 22] return xs[0..stop()].length}')
    binary = tmp_path / 'bounds'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode != 0 and 'slice' in ran.stderr, ran.stdout + ran.stderr



@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('name', ['optional_values', 'include_bytes', 'array_moves', 'object_fields', 'object_nested', 'array_elements', 'dict_runtime'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_existing_program(compiler, tmp_path, release, name, target):
    source = Path(__file__).resolve().parents[2] / f'dewy/tests/{name}.dewy'
    binary = tmp_path / 'optional'
    flags = ['--release'] if release else []
    node = shutil.which('node')
    if target == 'wasm':
        if node is None: pytest.skip('Node is needed for web execution')
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=30, cwd=tmp_path, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_grapheme_conformance(compiler, tmp_path, release, target):
    """Independent Unicode expectations, with one compiler process per mode/target."""
    root = Path(__file__).resolve().parents[2]
    cases = [(b'', [0])]
    for line in (root / 'tests/data/GraphemeBreakTest-16.0.0.txt').read_text().splitlines():
        tokens = line.split('#')[0].split()
        if not tokens:
            continue
        data = bytearray()
        boundaries = []
        for token in tokens:
            if token == '÷':
                boundaries.append(len(data))
            elif token != '×':
                data.extend(chr(int(token, 16)).encode())
        cases.append((bytes(data), boundaries))
    # Exhaust the ASCII shortcut, including the CR/LF exception.
    cases.extend((bytes([a, b]), [0, 2] if (a, b) == (13, 10) else [0, 1, 2])
                 for a in range(128) for b in range(128))
    cases.extend((data, None) for data in [b'\x80', b'\xc0\xaf', b'\xc1\xbf', b'\xc2',
                 b'\xe0\x80\x80', b'\xed\xa0\x80', b'\xf0\x80\x80\x80', b'\xf4\x90\x80\x80',
                 b'\xf5\x80\x80\x80', b'\xe2\x82', b'\xc2A', b'\xff'])
    cases.extend((prefix + invalid, None)
                 for prefix in [b'A', b'AB', b'\r', b'\r\n', b'\r\nA']
                 for invalid in [b'\x80', b'\xc2', b'\xed\xa0\x80', b'\xf4\x90\x80\x80'])
    (tmp_path / 'cases.bin').write_bytes(b''.join(struct.pack('<I', len(data)) + data for data, _ in cases))
    expected = ['invalid' if boundaries is None else ','.join(map(str, boundaries)) for _, boundaries in cases]
    (tmp_path / 'iteration.dewy').write_text('''stream_clusters=(text:string):>array<string>=>[loop c in text c]
''')
    source = tmp_path / 'conformance.jo'
    source.write_text('''use 'iteration.dewy'
main = ():
    data_ = embed("cases.bin")
    offset = 0
    loop offset < data_.len():
        size = __grapheme_word(data_, offset)
        offset += 4
        text = str_from_bytes(data_[offset..offset + size))
        offset += size
        decoded = __dewy_decode_utf8(bytes(text))
        if let bounds = grapheme_boundaries(text):
            assert(decoded != none and decoded! == text)
            assert(__dewy_string_length(text) == bounds.len() - 1)
            clusters = graphemes(text)
            assert(clusters.len() == bounds.len() - 1)
            assert(join(clusters, "") == text)
            assert(stream_clusters(text) == clusters)
            loop i in [0..clusters.len()):
                assert(__dewy_string_index(text, i) == clusters[i])
                assert(__dewy_string_slice(text, i, i + 1, false, true) == clusters[i])
                assert(__dewy_string_slice(text, i, i, true, true) == clusters[i])
            parts: str[]
            loop boundary in bounds: parts.push("{boundary}")
            print(join(parts, ","))
        else:
            assert(decoded == none)
            print("invalid")
''')
    binary = tmp_path / 'conformance'
    flags = ['--release'] if release else []
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed for web conformance')
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
    assert ran.stdout.splitlines() == expected


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_streaming_graphemes(compiler, tmp_path, target, release):
    source = tmp_path / 'stream.dewy'
    source.write_text('''let calls:int64=0
let shared="abc"
input=()=>{calls+=1 return shared}
replace=()=>{shared="changed" return "12"}
first=(text:string):>string=>{loop c in text return c return ""}
main=()=>{
    let before=alloc_count()
    {
        let large=repeat("a" 20000)
        let ready=alloc_count()
        loop c in large {
            # A loop keeps one cluster, not an array of 20,000 cluster strings.
            if alloc_count()-ready >? 12 return 1
            if c not=? "a" return 2
            break
        }
        let sum:int64=0
        loop i in 0.. and c in large {if i =? 3 break if i =? 1 continue sum+=i+bytes(c).length}
        if sum not=? 4 return 3
        let saved:array<string>=[]
        loop c in "é👩‍👩‍👧‍👦🇺🇸" {saved.push(c) c="changed"}
        if saved not=? ["é" "👩‍👩‍👧‍👦" "🇺🇸"] return 4
        let seen=""
        loop c in input() {shared="replacement" seen+=c}
        if calls not=? 1 or seen not=? "abc" return 5
        shared="abc"
        seen=""
        loop a in input() and b in replace() {seen+=a+b}
        if calls not=? 2 or seen not=? "a1b2" return 6
        let zipped=[loop a in "abc" and b in [1 2] a]
        if zipped not=? ["a" "b"] return 7
        let count:int64=0
        loop a in "" and b in "abc" {count+=1}
        loop a in "ab" and b in "cd" {loop c in "12" {if c =? "1" continue count+=1}}
        if count not=? 2 return 8
        if first("") not=? "" or first("🙂x") not=? "🙂" return 9
        # Foreign bytes are checked as visited; an untouched tail is not scanned.
        let bad_tail=str_from_bytes([97 98 99 255] as array<uint8>)
        if first(bad_tail) not=? "a" return 10
        loop i in [0..100) {if first(large) not=? "a" return 11}
        if alloc_count()-ready >? 25 return 12
    }
    if alloc_count() not=? before return 13
    return 42
}
''')
    binary = tmp_path / 'stream'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web streaming checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'stream.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('expression', ['s[2]', 's[-1]', 's[0..2]', 's[2..1)', 's[0..9223372036854775807]'])
def test_core_grapheme_bounds_panic(compiler, tmp_path, expression):
    source = tmp_path / 'bounds.dewy'
    source.write_text(f'main=()=>{{let s="é🙂" printl({expression})}}')
    binary = tmp_path / 'bounds'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode != 0 and 'out of bounds' in ran.stderr, ran.stdout + ran.stderr


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_embedded_png(compiler, tmp_path, release, target):
    """A Dewy asset declaration feeds the inherited image decoder on both targets."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    asset = tmp_path / 'pixel.png'
    asset.write_bytes(b'\x89PNG\r\n\x1a\n'
                      + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
                      + chunk(b'IDAT', zlib.compress(bytes([0, 42, 0, 0, 255])))
                      + chunk(b'IEND', b''))
    source = tmp_path / 'image.dewy'
    source.write_text('''$include_bytes(p"pixel.png") as pixel
main=()=>{let image=load_image(pixel)
return if image.width =? 1 and image.height =? 1 and image.pixels.length =? 4 image.pixels[0] as int64 else 1}
''')
    binary = tmp_path / 'image'
    flags = ['--release'] if release else []
    node = shutil.which('node')
    if target == 'wasm':
        if node is None:
            pytest.skip('Node is needed for web execution')
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    # The emitted program is self-contained; decoding must not read the source asset.
    asset.unlink()
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_physics_scene(compiler, tmp_path, target, release):
    node = shutil.which('node')
    if target == 'wasm' and node is None:
        pytest.skip('Node is needed to execute the generated web runner')
    model = Path(__file__).resolve().parents[2] / 'examples/sloppy_core/physics_scene.dewy'
    shutil.copy2(model, tmp_path)
    source = tmp_path / 'physics_test.dewy'
    source.write_text('''import physics as dynamics
from p"physics_scene.dewy" import fresh, advance, add_ball
main=()=>{
    let scene=fresh()
    if scene.world.bodies().length not=? 57 return 1
    let original=scene
    let ball=add_ball(@scene vec2(50 100) 12)
    loop i in [0..120) {advance(@scene 1.0/120.0)}
    if scene.world.bodies().length not=? 58 or original.world.bodies().length not=? 57 return 2
    let fallen=scene.world.pos(ball)
    if fallen.y <? 400.0 or fallen.y >? 680.0 return 3
    if original.rope is? dynamics.Joint {
        let ends=original.world.ends(original.rope)
        if ends[1].x not=? 640.0 or ends[1].y not=? 160.0 return 4
    } else return 5
    let joint=scene.world.drag(ball fallen)
    scene.world.drag_to(joint vec2(200 200))
    loop i in [0..120) {advance(@scene 1.0/120.0)}
    let moved=scene.world.pos(ball)
    if moved.x <? 100.0 or moved.y >? 400.0 return 6
    scene.world.remove(joint)
    scene.world.remove(ball)
    if scene.world.bodies().length not=? 57 return 7
    return 42
}''')
    binary = tmp_path / 'physics_test'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.mark.parametrize('style', ['namespace', 'selected'])
def test_core_library_import(compiler, tmp_path, style):
    source = tmp_path / 'import_test.dewy'
    declaration, name = ('import physics as dynamics', 'dynamics.World') if style == 'namespace' else (
        'from physics import World as Space', 'Space')
    source.write_text(f'{declaration}\nmain=()=>{{let world={name}[] return world.iterations+34}}')
    binary = tmp_path / 'import_test'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('indent', ['    ', '\t'], ids=['spaces', 'tabs'])
@pytest.mark.parametrize('use_invalid', [False, True], ids=['deferred', 'called'])
def test_core_conditional_library_bodies(compiler, tmp_path, target, release, indent, use_invalid):
    library = tmp_path / 'lib'
    library.mkdir()
    for item in (compiler.parent.parent / 'lib').iterdir():
        if item.name != 'std':
            (library / item.name).symlink_to(item, target_is_directory=item.is_dir())
    (library / 'std').mkdir()
    for item in (compiler.parent.parent / 'lib/std').iterdir():
        (library / 'std' / item.name).symlink_to(item)
    # Declaration branches, sibling bodies, multiline strings, comments and local
    # closures must keep their boundaries when library bodies are parsed on demand.
    text = '''when true:
    when false:
        conditional_pick = () -> int:
            return )
    else when TARGET == "wasm":
        conditional_pick = () -> int:
            text = """first
unindented text
last"""
            return if len(text) > 0: 40 else: 0
    else:
        conditional_pick = () -> int:
            return 40
# A comment outside the function does not end the declaration branch.
    conditional_tail = () -> int:
        f = (x: int) -> int:
            when true:
                return x + 1
        return f(1)
    conditional_invalid = () -> int:
        return )
conditional_runtime = () -> int:
    if true:
        local = (x: int) -> int:
            return x + 1
        return local(1) - 2
    else:
        local = (x: int) -> int:
            return x + 2
        return local(1) - 3
'''
    if indent == '\t':
        text = '\n'.join(indent * ((len(line) - len(line.lstrip(' '))) // 4)
                         + line.lstrip(' ') for line in text.split('\n'))
    fixture = library / 'std/conditional_bodies.jo'
    fixture.write_text(text)
    source = tmp_path / 'main.dewy'
    expression = 'conditional_invalid()' if use_invalid else (
        'conditional_pick()+conditional_tail()+conditional_runtime()')
    source.write_text(f'main=()=>{expression}\n')
    binary = tmp_path / 'program'
    flags = ['--release'] if release else []
    env = {**os.environ, 'DEWY_CORE_LIB': str(library)}
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           env=env, capture_output=True, text=True, timeout=30, check=False)
    if use_invalid:
        line = text.splitlines().index('        return )'.replace('    ', indent), 5) + 1
        assert built.returncode != 0
        assert f'{fixture}:{line}:' in built.stderr, built.stderr
        return
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web library parsing checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'conditional.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('source_text', [
    'divide=(a b)=>a/b\nmain=()=>if divide(3.0 2.0) =? 1.5 42 else 1',
    'BigInt:type=[value:int64]\n__truediv__=(a:BigInt b:BigInt)=>a.value//b.value\nmain=()=>BigInt[84]/BigInt[2]',
], ids=['float', 'custom'])
def test_core_division_without_exact_libraries(compiler, tmp_path, source_text):
    library = tmp_path / 'lib'
    library.mkdir()
    for item in (compiler.parent.parent / 'lib').iterdir():
        if item.name not in ('bigint.dewy', 'rational.dewy'):
            (library / item.name).symlink_to(item, target_is_directory=item.is_dir())
    source = tmp_path / 'main.dewy'
    source.write_text(source_text)
    binary = tmp_path / 'program'
    env = {**os.environ, 'DEWY_CORE_LIB': str(library)}
    built = subprocess.run([compiler, 'build', source, '-o', binary, '--release'], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('entry', ['body', 'global', 'unused-constant'])
def test_core_exact_division_module_initialization(compiler, tmp_path, target, release, entry):
    library = tmp_path / 'lib'
    library.mkdir()
    for item in (compiler.parent.parent / 'lib').iterdir():
        if item.name != 'rational.dewy':
            (library / item.name).symlink_to(item, target_is_directory=item.is_dir())
    # An observable library initializer checks dependency order when a language
    # operation first discovers a module during function/global checking.
    (library / 'seed.dewy').write_text('let seed:int64=39\nprintl"seed"\n')
    (library / 'rational.dewy').write_text('''from seed import seed
let base=seed+1
printl"rational"
rational=(a b):>int64=>a+b+base
''')
    (tmp_path / 'helper.dewy').write_text('const offset=1\n')
    bodies = {
        'body': 'main=()=>1/2-offset',
        'global': 'let ratio=1/2\nmain=()=>ratio-offset',
        'unused-constant': 'const unused=1/2\nmain=()=>42',
    }
    source = tmp_path / 'main.dewy'
    source.write_text('from helper import offset\nprintl"main"\n' + bodies[entry] + '\n')
    binary = tmp_path / 'program'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    env = {**os.environ, 'DEWY_CORE_LIB': str(library)}
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('Node is needed for web module initialization checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'modules.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['seed', 'rational', 'main']


@pytest.mark.parametrize(('expression', 'diagnostic'), [
    ('pair[0]+pair[1].length', None),
    ('pair[-1]', 'tuple index out of range'),
    ('pair[2]', 'tuple index out of range'),
    ('pair[i]', 'tuple index must be an integer literal'),
])
def test_core_tuple_interop(compiler, tmp_path, expression, diagnostic):
    (tmp_path / 'helper.jo').write_text('pair = () -> (int, str): (39, "abc")')
    source = tmp_path / 'tuple.dewy'
    source.write_text(f'import p"helper.jo"\nmain=()=>{{let pair=helper.pair() let i:int64=0 return {expression}}}')
    binary = tmp_path / 'tuple'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    if diagnostic:
        assert built.returncode != 0 and diagnostic in built.stderr, built.stdout + built.stderr
    else:
        assert built.returncode == 0, built.stdout + built.stderr
        assert subprocess.run([binary], timeout=10, check=False).returncode == 42


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
@pytest.mark.parametrize('mismatch', [False, True])
@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('parameter', [False, True], ids=['binding', 'parameter'])
def test_core_unpack_tuple_and_length_guard(compiler, tmp_path, target, release, mismatch, nested, parameter):
    (tmp_path / 'helper.jo').write_text('''pair = () -> (int, str): (39, "abc")
nested = () -> ((int, str), int[]): ((39, "abc"), [0])
pairs = () -> (str, int[])[]: [("a", [20, 1]), ("b", [2, 19])]''')
    source = tmp_path / 'unpack.dewy'
    if mismatch:
        program = ('main=()=>{let [[first second] [_]]=[[42] [0]] return first+second}' if nested else
                   'main=()=>{let [first second]=[42] return first+second}')
    else:
        program = ('''main=()=>{let [[count text] [extra]]=helper.nested()
let total:int64=0
loop [key [x y]] in helper.pairs() {total+=x+y}
loop i in [0..2) and [key [x y]] in helper.pairs() {total+=x+y}
if total not=? 84 return 1
return count+text.length+extra}''' if nested else
                   'main=()=>{let [count:float64 text:string]=helper.pair() return if count is?float64 (count as int64)+text.length else 1}')
    if parameter:
        if mismatch:
            program = ('sum=([[first second] [_]]:array<array<int64>>):>int64=>first+second\nmain=()=>sum([[42] [0]])' if nested else
                       'sum=([first second]:array<int64>):>int64=>first+second\nmain=()=>sum([42])')
        else:
            program = ('sum=([[count text] [extra]])=>count+text.length+extra\nmain=()=>sum(helper.nested())' if nested else
                       'sum=([count:float64 text:string])=>if count is?float64 (count as int64)+text.length else 1\nmain=()=>sum(helper.pair())')
    source.write_text('import p"helper.jo"\n' + program)
    binary = tmp_path / 'unpack'
    node = shutil.which('node')
    if target == 'wasm' and node is None:
        pytest.skip('Node is needed for web execution')
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    if mismatch:
        assert ran.returncode != 0 and 'unpacking requires exactly 2 elements' in ran.stderr, ran.stdout + ran.stderr
    else:
        assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


def test_core_web_pointer_lock_events():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is required for the web input event check')
    script = Path(__file__).with_name('core_web_input.cjs')
    result = subprocess.run([node, script], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
