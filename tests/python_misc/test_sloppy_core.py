"""Expected user behavior for the experimental source-level core."""
import os
import shutil
import struct
import subprocess
import zlib
from html.parser import HTMLParser
from pathlib import Path

import pytest

CASES = {
    'answer': 'main=():>int64=>42',
    'syntax-coefficients': '''twice=(x:int64)=>2x
main=()=>{let x:int64=19 return twice(x)+2(x-17)}''',
    'syntax-coefficient-call': '''value=()=>21
main=()=>2value()''',
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
    'named-duplicate': ('add=(x:int64 y:int64)=>x+y\nmain=()=>add(40 x=2)', 'given twice'),
    'match-incomplete': ('main=()=>match 42 {<42>=>42}', 'not exhaustive'),
    'match-incomplete-statement': ('main=()=>{match true {<true>=>42} return 42}', 'not exhaustive'),
    'match-wrong-type': ('main=()=>match 42 {n:string=>n.length _=>42}', 'not a member'),
    'match-refinement': ('main=()=>match 42 {n:int64<n >? 0>=>n _=>0}', 'does not yet support'),
    'missing-place': ('bump=(@x:int64):>void=>{x+=2}\nmain=():>int64=>{let x:int64=40 bump(x) return x}', 'needs `@`'),
    'unbounded-int': ('main=():>int=>42', 'unbounded integer'),
    'integer-division': ('main=():>int64=>85/2', 'integer /'),
    'literal-too-large': ('main=()=>18446744073709551616', 'exceeds uint64'),
    'hex-too-large': ('main=()=>0x10000000000000000', 'exceeds uint64'),
    'negative-too-large': ('main=()=>-9223372036854775809', 'exceeds int64'),
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
    'comprehension-mixed': ('main=()=>[loop i in [1 2] if i =? 1 "a"->2 else 3]', 'cannot mix'),
    'syntax-unclosed-block': ('main=()=>{42', "expected '}'"),
    'syntax-mismatched-block': ('main=()=>[42}', 'expected an expression'),
    'syntax-unclosed-string': ('main=()=>"hello', 'unterminated string'),
    'syntax-empty-interpolation': ('main=()=>"{}"', 'expected an expression'),
    'syntax-missing-member': ('main=()=>value.', 'expected a member name'),
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


@pytest.mark.parametrize('name', CASES)
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_values(compiler, tmp_path, name, release):
    source = tmp_path / f'{name}.dewy'
    source.write_text(CASES[name])
    binary = tmp_path / name
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    result = subprocess.run([binary, 'extra'], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 42, (result.returncode, result.stdout, result.stderr)
    if name == 'unicode':
        assert result.stdout == 'é🙂 42\n'


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


@pytest.mark.parametrize('game', ['paddle', 'physics'])
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


@pytest.mark.parametrize('name', [*[name for name in CASES if name.startswith(('match-', 'named-', 'argument-', 'conversion-', 'record-', 'default-reference-', 'comprehension-'))], 'unsigned-constant-math', 'narrow-integers', 'scientific', 'optional-managed-copy', 'optional-union', 'array-slices', 'slice-bound-side-effect', 'slice-replaced-source', 'grapheme-length', 'grapheme-index', 'grapheme-slices', 'grapheme-loop', 'grapheme-zipped-loop', 'grapheme-bound-side-effect', 'panic-ended-search', 'binary-literals', 'utf8-decode', 'utf8-copy'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_value_web(compiler, tmp_path, name, release):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is needed to execute the generated web runner')
    source = tmp_path / 'numeric.dewy'
    source.write_text(CASES[name])
    binary = tmp_path / 'numeric'
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '--target', 'wasm', '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    scripts = Scripts()
    scripts.feed(binary.with_suffix('.html').read_text())
    runner = tmp_path / 'runner.cjs'
    runner.write_text('\n'.join(scripts.parts))
    ran = subprocess.run([node, runner], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)



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
@pytest.mark.parametrize('name', ['optional_values', 'include_bytes', 'array_moves', 'object_fields', 'object_nested', 'array_elements'])
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
    source = tmp_path / 'conformance.jo'
    source.write_text('''main = ():
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
