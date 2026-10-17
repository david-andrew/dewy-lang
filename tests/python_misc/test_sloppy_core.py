"""Expected user behavior for the experimental source-level core."""
import base64
import math
import os
import random
import re
import shutil
import struct
import subprocess
import zlib
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tools.sloppy_core.benchmark_apps import CHECKSUMS_1000, prepare_source

CASES = {
    'answer': 'main=():>int64=>42',
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
let bump=()=>{xs[0]+=1} bump() bump() return if original[0]=?40 xs[0] else 1}''',
    'type-alias': 'Count:type=int64\nmain=()=>{let x:Count=42 return x}',
    'union': '''Choice:type=int64|string
value=(x:Choice):>int64=>if x is? int64 x else 0
main=()=>value(42)+value("ignored")''',
    'union-inverse': '''value=(x:int64|string):>int64=>if x isnt? int64 0 else x
main=()=>value(42)+value("ignored")''',
    'optional-return': '''choose=(yes:bool):>int64?=>if yes 42 else none
main=()=>{let a=choose(true) let b=choose(false)
return if a is? int64 and b is? none a else 1}''',
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
    'dictionary-length': 'main=()=>{let a=["a"->1 "b"->2] return a.length+40}',
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
    'unpack-array': 'main=()=>{let [x y]=[20 22] return x+y}',
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
    'match-incomplete': ('main=()=>match 42 {<42>=>42}', 'not exhaustive'),
    'match-incomplete-statement': ('main=()=>{match true {<true>=>42} return 42}', 'not exhaustive'),
    'match-wrong-type': ('main=()=>match 42 {n:string=>n.length _=>42}', 'not a member'),
    'match-refinement': ('main=()=>match 42 {n:int64<n >? 0>=>n _=>0}', 'does not yet support'),
    'missing-place': ('bump=(@x:int64):>void=>{x+=2}\nmain=():>int64=>{let x:int64=40 bump(x) return x}', 'needs `@`'),
    'unbounded-int': ('main=():>int=>42', 'unbounded integer'),
    'integer-division': ('main=():>int64=>85/2', 'integer /'),
    'literal-too-large': ('main=():>uint64=>18446744073709551616', 'type mismatch'),
    'hex-too-large': ('main=():>uint64=>0x10000000000000000', 'type mismatch'),
    'negative-too-large': ('main=():>int64=>-9223372036854775809', 'type mismatch'),
    'signed-literal-overflow': ('main=():>int64=>0xffffffffffffffff', 'does not fit'),
    'narrow-literal-overflow': ('main=()=>{let x:uint8=256 return x}', 'does not fit'),
    'float-literal-overflow': ('main=()=>1e309', 'exceeds float64'),
    'unary-plus-text': ('main=()=>+"text"', "needs a number"),
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
    'unpack-duplicate': ('main=()=>{let [x x]=[20 22] return x}', 'duplicate unpacking name'),
    'unpack-missing-field': ('main=()=>{let [missing]=[x=42] return missing}', 'no field'),
    'unpack-record-discard': ('main=()=>{let [_]=[x=42] return 0}', 'leave unwanted fields out'),
    'unpack-nested': ('main=()=>{let [[x]]= [[42]] return x}', 'nested or annotated'),
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


@pytest.fixture(scope='module')
def compiler():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER to the experimental source-level core')
    return Path(value).resolve(strict=True)


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


def run_value_batch(compiler, directory, cases, release, target):
    """Keep source modules independent while amortizing compiler/runtime startup."""
    imports, body = [], []
    names = list(cases)
    for i, (name, source) in enumerate(cases.items()):
        (directory / f'{name}.dewy').write_text(source)
        imports.append(f'from p"{name}.dewy" import (main as case_{i})')
        body.extend([f'printl"__DEWY_CASE_BEGIN__:{name}"',
                     f'let result_{i}=case_{i}()',
                     f'printl"__DEWY_CASE_END__:{name}:{{result_{i}}}"'])
    source = directory / 'batch.dewy'
    source.write_text('\n'.join(imports) + '\nmain=():>void=>{\n' + '\n'.join(body) + '\n}\n')
    binary = directory / 'batch'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    if built.returncode:
        message = f'Batch build failed; sources in {directory}\n{built.stdout}{built.stderr}'
        return {name: (None, message) for name in names}
    command = [binary, 'extra']
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed to execute the generated web runner')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = directory / 'batch.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    if ran.returncode:
        message = f'Batch exited {ran.returncode}; sources in {directory}\n{ran.stdout}{ran.stderr}'
        return {name: (None, message) for name in names}
    outcomes = {}
    active, output = None, []
    for line in ran.stdout.splitlines(keepends=True):
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
            outcomes[name] = (None, f'Missing result for {name}; sources in {directory}\n{ran.stdout}{ran.stderr}')
    return outcomes


@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_value_batch_results(compiler, tmp_path, target):
    cases = {
        'first': 'value=1\nmain=()=>{value+=1 printl"first 🙂" return 42}',
        'wrong': 'value=40\nmain=()=>{printl"wrong result" return 17}',
        'last': 'value=40\nmain=()=>if value =? 40 42 else 1',
    }
    outcomes = run_value_batch(compiler, tmp_path, cases, False, target)
    assert outcomes == {'first': ('42', 'first 🙂\n'), 'wrong': ('17', 'wrong result\n'),
                        'last': ('42', '')}


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('failure', ['compile', 'runtime'])
def test_core_value_batch_failures(compiler, tmp_path, target, failure):
    bad = ('main=()=>missing_batch_name' if failure == 'compile'
           else 'main=()=>{panic("intentional batch stop") return 42}')
    outcomes = run_value_batch(compiler, tmp_path,
                               {'first': 'main=()=>42', 'bad': bad, 'last': 'main=()=>42'}, False, target)
    assert all(code is None for code, _ in outcomes.values())
    for _, diagnostic in outcomes.values():
        assert str(tmp_path) in diagnostic
        assert ('bad.dewy' if failure == 'compile' else 'intentional batch stop') in diagnostic


@pytest.fixture(scope='module')
def value_batches(compiler, tmp_path_factory, request):
    # Collection has already applied -k / node selection. Compile only selected
    # cases, in groups of at most 16, and cache each group for its individual IDs.
    selected = {}
    for item in request.session.items:
        if item.module is not request.module:
            continue
        target = {'test_core_values': 'native', 'test_core_value_web': 'wasm'}.get(item.originalname)
        if target is not None:
            params = item.callspec.params
            selected.setdefault((target, params['release']), []).append(params['name'])
    groups = {}
    for (target, release), names in selected.items():
        for start in range(0, len(names), 16):
            group = tuple(names[start:start + 16])
            for name in group:
                groups[target, release, name] = group
    cached = {}

    def result(name, release, target):
        group = groups[target, release, name]
        key = target, release, group
        if key not in cached:
            directory = tmp_path_factory.mktemp(f'values-{target}-{"release" if release else "debug"}')
            cached[key] = run_value_batch(compiler, directory, {n: CASES[n] for n in group}, release, target)
        return cached[key][name]

    return result


@pytest.mark.parametrize('name', CASES)
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
    ('2^(-1)', 'negative integer exponent: use a rational or floating base'),
    ('(2 as uint64)^(-1)', 'negative integer exponent: use a rational or floating base'),
    ('bigint("12x")', 'invalid decimal integer'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_bigint_errors(compiler, tmp_path, expression, diagnostic, target, release):
    source = tmp_path / 'invalid.dewy'
    source.write_text(f'from bigint import bigint\nmain=():>void=>{{printl"{{{expression}}}"}}')
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
            pytest.skip('Node is needed for web bigint checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'invalid.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode != 0
    assert diagnostic in ran.stdout + ran.stderr


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_rational_arithmetic(compiler, tmp_path, target, release):
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
    source.write_text('''from rational import rational
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
''')
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


@pytest.mark.parametrize('expression, diagnostic', [
    ('rational(1 0)', 'rational denominator must be nonzero'),
    ('rational(1)/rational(0)', 'rational division by zero'),
    ('rational(1)//0', 'rational division by zero'),
    ('rational(1)%0', 'rational division by zero'),
    ('rational(0).pow(-1)', 'rational division by zero'),
    ('rational(0)^(-1)', 'rational division by zero'),
    ('rational("1/0")', 'invalid rational text'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_rational_errors(compiler, tmp_path, expression, diagnostic, target, release):
    source = tmp_path / 'invalid.dewy'
    source.write_text(f'from rational import rational\nmain=():>void=>{{printl"{{{expression}}}"}}')
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
            pytest.skip('Node is needed for web rational checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'invalid.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
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
    (tmp_path / 'constants.dewy').write_text('''const amount=123456789012345678901234567890
read=(value=amount)=>value+1
''')
    source = tmp_path / 'main.dewy'
    source.write_text('''from constants import amount, read
main=()=>if amount+1 =? read() and read(18446744073709551616) =? 18446744073709551617 42 else 1
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


@pytest.mark.parametrize('body', [
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
], ids=['changed-index', 'changed-length', 'skipped-check', 'next-iteration'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_optimizer_bounds(compiler, tmp_path, body, target, release):
    source = tmp_path / 'bounds.dewy'
    source.write_text(f'main=():>void=>{{{body}}}')
    binary = tmp_path / 'bounds'
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
            pytest.skip('Node is needed for web bounds checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'bounds.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
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
def test_core_unsigned_floor_arithmetic(compiler, tmp_path, target, release):
    maximum = (1 << 64) - 1
    numerators = [0, 1, 2, 127, 255, 65535, (1 << 32) - 1, 1 << 32,
                  (1 << 63) - 1, 1 << 63, maximum - 1, maximum]
    denominators = [1, 2, 3, 255, 1000000007, (1 << 32) - 1, 1 << 32, 1 << 63, maximum]
    powers = [1 << shift for shift in range(64)]
    constants = '\n'.join(f'printl"{{a//{b}}} {{a%{b}}}"' for b in powers)
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
    expected = [f'{a // b} {a % b}' for a in numerators for b in denominators + powers]
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
    constants = powers + [-3, 3, -129, 129, -1000000007, 1000000007, minimum, maximum]
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
    ('controls', '"\\a\\b\\v\\f\\0".length', '5'),
])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_string_literals(compiler, tmp_path, name, expression, expected, target, release):
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
def test_core_membership(compiler, tmp_path, name, program, target, release):
    source = tmp_path / f'{name}.dewy'
    source.write_text(program + '\nmain=():>void=>printl(probe())')
    binary = tmp_path / name
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
            pytest.skip('Node is needed for web membership checks')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / f'{name}.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == '42\n'


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
    return if one.value+b.identity<int64>(two.value) =? 42 and two.extra =? 2
        and nested.value[0] =? "one" and item.value =? "wrapped"
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


@pytest.mark.parametrize('case', ['history', 'managed-values', 'capacity', 'negative-index', 'past-end'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_ring_example(compiler, tmp_path, case, target, release):
    examples = Path(__file__).resolve().parents[2] / 'examples/sloppy_core'
    shutil.copy2(examples / 'ring.dewy', tmp_path / 'ring.dewy')
    source = tmp_path / 'main.dewy'
    if case == 'history':
        source.write_text((examples / 'history.dewy').read_text())
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
                              'Newest position: 112, 6\nRewind position: 12, 6\n')
    elif case == 'managed-values':
        assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
    else:
        assert ran.returncode != 0
        message = 'ring capacity must be positive' if case == 'capacity' else 'ring index out of bounds'
        assert message in ran.stdout + ran.stderr


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


@pytest.mark.parametrize('name', ERRORS)
def test_core_rejects(compiler, tmp_path, name):
    body, diagnostic = ERRORS[name]
    source = tmp_path / f'{name}.dewy'
    source.write_text(body)
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode != 0 and diagnostic in built.stderr, built.stdout + built.stderr
    assert str(source) in built.stderr
    assert not binary.exists()


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
@pytest.mark.parametrize('style', ['selected', 'namespace', 'module-alias', 'name-alias'])
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


@pytest.mark.parametrize('game', ['paddle', 'physics', 'forest'])
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


@pytest.mark.parametrize('game', ['paddle', 'physics', 'forest'])
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


def test_core_check_and_format_boundary(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    text = 'unused=()=>missing\nmain=()=>42'
    source.write_text(text)
    checked = subprocess.run([compiler, 'check', source], capture_output=True,
                             text=True, timeout=10, check=False)
    assert checked.returncode != 0 and 'unknown' in checked.stderr, checked.stdout + checked.stderr
    formatted = subprocess.run([compiler, 'fmt', source], capture_output=True,
                               text=True, timeout=10, check=False)
    assert formatted.returncode != 0 and 'not implemented' in formatted.stderr
    assert source.read_text() == text


@pytest.mark.parametrize('command', ['update', 'upgrade', 'repl', 'add'])
def test_core_unavailable_cli(compiler, tmp_path, command):
    result = subprocess.run([compiler, command], cwd=tmp_path, capture_output=True,
                            text=True, timeout=5, check=False)
    assert result.returncode == 2
    assert 'dewy-core:' in result.stderr
    assert not list(tmp_path.iterdir())


def test_core_cli_identity(compiler):
    result = subprocess.run([compiler, '--version'], capture_output=True, text=True,
                            timeout=5, check=False)
    assert result.returncode == 0 and result.stdout.startswith('dewy-core ')
    result = subprocess.run([compiler, '--help'], capture_output=True, text=True,
                            timeout=5, check=False)
    assert result.returncode == 0 and 'file.dewy' in result.stderr


@pytest.mark.parametrize('kind', ['game', 'program'])
def test_core_new_project(compiler, tmp_path, kind):
    project = tmp_path / 'project with spaces'
    made = subprocess.run([compiler, 'new', project, kind], capture_output=True,
                          text=True, timeout=5, check=False)
    assert made.returncode == 0, made.stdout + made.stderr
    source = project / 'main.dewy'
    assert source.is_file() and (project / 'README.md').is_file()
    assert not list(project.glob('*.jo'))
    binary = project / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_SOFTWARE='1', SLOPPY_FRAMES='3', SLOPPY_SCREENSHOT=str(project / 'frame.png'))
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


@pytest.mark.parametrize('name', [*[name for name in CASES if name.startswith(('optimizer-', 'power-', 'rational-', 'bigint-', 'overload-group-', 'generic-', 'match-', 'named-', 'argument-', 'conversion-', 'record-', 'default-reference-', 'comprehension-', 'unpack-'))], 'floor-literal-inference', 'unsigned-constant-math', 'narrow-integers', 'scientific', 'optional-managed-copy', 'optional-union', 'array-slices', 'slice-bound-side-effect', 'slice-replaced-source', 'grapheme-length', 'grapheme-index', 'grapheme-slices', 'grapheme-loop', 'grapheme-zipped-loop', 'grapheme-bound-side-effect', 'panic-ended-search', 'binary-literals', 'utf8-decode', 'utf8-copy'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_value_web(value_batches, name, release):
    code, output = value_batches(name, release, 'wasm')
    assert code == '42', f'{name}: {code}\n{output}'



def test_core_slice_bounds_panic(compiler, tmp_path):
    source = tmp_path / 'bounds.dewy'
    source.write_text('end=()=>9\nmain=()=>{let xs=[20 22] return xs[0..end()].length}')
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
def test_core_unpack_tuple_and_length_guard(compiler, tmp_path, target, release, mismatch):
    (tmp_path / 'helper.jo').write_text('pair = () -> (int, str): (39, "abc")')
    source = tmp_path / 'unpack.dewy'
    source.write_text('''import p"helper.jo"
main=()=>{let [count text]=helper.pair() return count+text.length}''' if not mismatch else
                      'main=()=>{let [first second]=[42] return first+second}')
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
