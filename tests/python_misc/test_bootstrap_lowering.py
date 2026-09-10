"""Native storage/legalization executes scalar and array programs.

This deliberately enters below the full validation driver; it is not a public
compiler command and does not authorize arbitrary unchecked source emission.
"""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ('let main=():>int64=>{let twice=(x:int64):>int64=>x*2 return twice(21)}', 42),
    ('let main=():>int64=>{let n:int64=40 let read=():>int64=>n n=42 return read()}', 42),
    ('let main=():>int64=>{let n:int64=40 let first=():>int64=>second() let second=():>int64=>n+2 return first()}', 42),
    ('let main=():>int64=>{let n:int64=42 let read=(value:int64=n):>int64=>value return read()}', 42),
    ('let main=():>int64=>{let n:int64=40 let outer=(x:int64):>int64=>{let inner=():>int64=>n+x return inner()} return outer(2)}', 42),
    ('let main=():>int64=>{let base:int64=42 let even=(n:int64):>int64=>if n=?0 base else odd(n-1) let odd=(n:int64):>int64=>if n=?0 0 else even(n-1) return even(4)}', 42),
    ('Fn:type=(x:int64):>int64\nlet apply=(f:Fn):>int64=>f(21)\nlet main=():>int64=>{let twice=(x:int64):>int64=>x*2 return apply(@twice)}', 42),
    ('Point:type=[x:int64 y:int64]\nlet main=():>int64=>{let value=Point[20 22] return value.x+value.y}', 42),
    ('let main=():>int64=>{let value=[x=20 y=x+2] return value.x+value.y}', 42),
    ('Outer:type=[tag:uint8 inner:[x:int64] tail:uint8]\nlet main=():>int64=>{let value=Outer[1 [x=40] 2] let copy=value copy.inner.x=99 return value.inner.x+(copy.tail as int64)}', 42),
    ('Box:type=[values:array<int64>]\nlet main=():>int64=>{let value=Box[[40 2]] let copy=value copy.values[0]=99 return value.values[0]+copy.values[1]}', 42),
    ('Base:type=type of [x:int64]\nChild:type=type of Base & [y:int64]\nWide:type=type of Base & [a:int64 b:int64 c:int64]\nlet main=():>int64=>{let value:Base=Child[40 2] let copy=value if copy is? Child return copy.x+copy.y return 0}', 42),
    ('Root:type=[x:int64]\nMint:type=type of Root\nChild:type=type of Mint & [y:int64]\nlet main=():>int64=>{let value:Root=Child[40 2] let copy=value if copy is? Child return copy.x+copy.y return 0}', 42),
    ('Fn:type=(x:int64):>int64\nBox:type=[f:Fn]\nlet twice=(x:int64):>int64=>x*2\nlet main=():>int64=>{let box=Box[@twice] return box.f(21)}', 42),

    ('let main=():>int64=>{let values:array<int64>=[20 22] return values[0]+values[1]}', 42),
    ('let main=():>int64=>{let values:array<int64>=[40 2] let copy=values copy[0]=99 return values[0]+copy[1]}', 42),
    ('let main=():>int64=>{let values:array<int64>=[40 2] let copy:array<int64>=[0 0] copy=values copy[0]=99 return values[0]+copy[1]}', 42),
    ('let main=():>int64=>{let values:array<bool>=[false true] values[0]=values[1] return if values[0] and values[1] 42 else 0}', 42),
    ('let main=():>int64=>{let values:array<uint8>=[250 48] return (values[0]+values[1]) as int64}', 42),
    ('let main=():>int64=>{let values:array<int64>=[] return values.length+42}', 42),
    ('let main=():>int64=>{let values:array<int64>=[40 2] values=values return values[0]+values[1]}', 42),
    ('let main=():>int64=>{let memory=__alloca__(8) __store_i64__(42 memory) return __load_i64__(memory)}', 42),
    ('Fn:type=(x:int64):>int64\nlet twice=(x:int64):>int64=>x*2\nlet apply=(f:Fn=@twice):>int64=>f(21)\nlet main=():>int64=>apply()', 42),

    ('let f=(flag:bool=true):>int64=>if flag 42 else 0\nlet main=():>int64=>f()', 42),
    ('let seed:int64=0\nlet tick=():>bool=>{seed+=1 return seed <? 4}\nlet main=():>int64=>{loop tick() {} return seed+38}', 42),
    ('let seed:int64=0\nlet tick=():>bool=>{seed+=1 return false}\nlet main=():>int64=>{loop tick() {} else {seed+=41} return seed}', 42),
    ('let seed:int64=0\nlet tick=():>bool=>{seed+=1 return true}\nlet f=(flag:bool):>bool=>flag and tick()\nlet main=():>int64=>{f(false); f(true); return seed+41}', 42),
    ('let seed:int64=0\nlet tick=():>bool=>{seed+=1 return true}\nlet f=(flag:bool):>bool=>flag nor tick()\nlet main=():>int64=>{f(true); f(false); return seed+41}', 42),

    ('Fn:type=(x:int64):>int64\nlet apply=(f:Fn x:int64):>int64=>f(x)\nlet twice=(x:int64):>int64=>x*2\nlet main=():>int64=>apply(@twice 21)', 42),
    ('let add=(x:int64 y:int64=2):>int64=>x+y\nlet main=():>int64=>add(40)', 42),
    ('let add=(x:int64 y:int64=9):>int64=>x+y\nlet main=():>int64=>add(y=2 x=40)', 42),
    ('let combine=(left:int64 scale:int64=2 right:int64):>int64=>left+right*scale\nlet main=():>int64=>combine(10 right=16)', 42),
    ('let seed:int64=0\nlet next=():>int64=>{seed+=1 return seed}\nlet choose=(x:int64=next()):>int64=>x\nlet main=():>int64=>{choose(99); choose(); choose(); return seed+40}', 42),
    ('let seed:int64=0\nlet next=():>int64=>{seed+=1 return seed}\nlet difference=(x:int64 y:int64):>int64=>x-y\nlet main=():>int64=>difference(y=next() x=next())+41', 42),

    ('', 0),
    ('Word:type=int64\nlet main=():>Word=>42', 42),
    ('let main=():>int64=>42', 42),
    ('let score:int64=40\nlet main=():>int64=>score+2', 42),
    ('let main=():>int64=>twice(21)\nlet twice=(x:int64):>int64=>x*2', 42),
    ('let x:int64=4\nlet main=():>int64=>{let x:int64=40\nx+=2\nreturn x}', 42),
    ('let f=(x:int64):>int64=>{if x >? 0 return 42\nreturn 9}\nlet main=():>int64=>f(1)', 42),
    ('let main=():>int64=>{let i:int64=0\nloop i <? 42 {i+=1}\nreturn i}', 42),
    ('let main=():>int64=>{let x:uint8=250\nx+=48\nreturn x as int64}', 42),
    ('let main=():>int64=>{let x:int64=63\nx and=42\nreturn x}', 42),
]


# Exercise the actual allocator source used by the prelude, through native
# checking/lowering as well. Selecting its binding is this kernel driver's
# explicit stand-in for the full module driver's runtime identity lookup.
SYSTEM = (ROOT / 'library/linux/system.dewy').read_text()
ARENA = SYSTEM[SYSTEM.index('let _arena_cursor:'):SYSTEM.index('# Regions —')]
ARENA_CASES = [
    ("let same=(a:string|none b:string):>bool=>a =? b\nlet main=():>int64=>if same('a' 'a') and not same(none 'a') and not same('b' 'a') 42 else 0", 42),
    ("let same=(a:int64|string|none b:none|string|int64):>bool=>a =? b\nlet main=():>int64=>if same(3 3) and same('a' 'a') and same(none none) and not same(3 'a') and not same(none 3) 42 else 0", 42),
    ("let different=(a:int64|none b:none|int64):>bool=>a not=? b\nlet main=():>int64=>if different(3 4) and different(none 3) and not different(3 3) and not different(none none) 42 else 0", 42),
    ("let calls:int64=0\nlet value:int64|none=none\nlet next=():>int64=>{calls+=1 value=3 return 3}\nlet main=():>int64=>{let answer=value =? next() return if not answer and calls =? 1 42 else 0}", 42),
    ("let calls:int64=0\nlet next=():>none=>{calls+=1 return none}\nlet same=(x:int64|none):>bool=>x =? next()\nlet main=():>int64=>{let answer=same(none) return if answer and calls =? 1 42 else 0}", 42),
    ("let main=():>int64=>{let d=['a' -> 40] d['a']+=2 return d['a']}", 42),
    ("let main=():>int64=>{let d=['a' -> 40] d['a'] += {d.pop('a'); 2} return d['a']}", 42),
    ("let calls:int64=0\nlet next=():>'a'=>{calls+=1 return 'a'}\nlet main=():>int64=>{let d:totaldict<'a' int64>=['a' -> 40] d[next()]+=2 return if calls=?1 d['a'] else 0}", 42),
    ('let read=(values:array<int64>):>int64=>{let bits=values[0] transmute uint64 return bits transmute int64}\nlet main=():>int64=>{let values:array<int64>=[42] let before=_arena_cursor let answer=read(values) return if before =? _arena_cursor answer else 0}', 42),
    # Growing a descriptor moves its element handles and returns only the
    # obsolete data block. The allocator must be able to reuse that block.
    ('let main=():>int64=>{let values:array<int64>=[40] let old=__load_i64__(values) values.push(2) let reused=_arena_alloc(8) return if reused =? old values[0]+values[1] else 0}', 42),
    ('let main=():>int64=>{let values:array<int64>=[40] let saved=values values.push(2) let reused=_arena_alloc(8) __store_i64__(99 reused) return saved[0]+values[1]}', 42),
    ('let identity=(values:array<int64>):>array<int64>=>values\nlet main=():>int64=>{let values:array<int64>=[42] let pointer=__load_i64__(identity(values)) __store_i64__(99 pointer) return values[0]}', 42),
    ('Box:type=[values:array<int64>]\nlet identity=(box:Box):>Box=>box\nlet main=():>int64=>{let box=Box[[42]] let pointer=__load_i64__(identity(box).values) __store_i64__(99 pointer) return box.values[0]}', 42),

    ('let change=(pointer:int64):>int64=>{__store_i64__(99 pointer) return 0}\nlet read=(values:array<int64> other:int64):>int64=>values[0]\nlet main=():>int64=>{let values:array<int64>=[42] let pointer=__load_i64__(values) return read(values change(pointer))}', 42),

    ('let read=(values:array<int64> other:int64):>int64=>values.length\nlet main=():>int64=>{let values:array<int64>=[40 2] return read(values values.pop)+40}', 42),

    # A raw address returned from a value parameter must refer to its private
    # snapshot; writing through it later cannot change the caller's array.
    ('let expose=(values:array<int64>):>int64=>__load_i64__(values)\nlet main=():>int64=>{let values:array<int64>=[42] let pointer=expose(values) __store_i64__(99 pointer) return values[0]}', 42),
    ('let read=(values:array<int64> other:int64):>int64=>values[0]\nlet main=():>int64=>{let values:array<int64>=[42] return read(values {values[0]=99; 0})}', 42),
    ('let counter:int64=0\nlet read=(values:array<int64>):>int64=>{counter+=1 return values[0]}\nlet main=():>int64=>{let values:array<int64>=[42] let before=_arena_cursor let answer=read(values) return if before =? _arena_cursor answer else 0}', 42),
    # Read-only calls borrow without allocation; overlapping places, later
    # argument writes and ambient global writes still require value snapshots.
    ('let read=(values:array<int64>):>int64=>values[0]\nlet main=():>int64=>{let values:array<int64>=[42] let before=_arena_cursor let answer=read(values) return if before =? _arena_cursor answer else 0}', 42),
    ('Box:type=[values:array<int64>]\nlet read=(box:Box):>int64=>box.values[0]\nlet main=():>int64=>{let box=Box[[42]] let before=_arena_cursor let answer=read(box) return if before =? _arena_cursor answer else 0}', 42),
    ('let change=(@values:array<int64>):>int64=>{values[0]=99 return 0}\nlet read=(values:array<int64> other:int64):>int64=>values[0]\nlet main=():>int64=>{let values:array<int64>=[40] return read(values change(@values))+2}', 42),
    ('let read=(values:array<int64> @other:array<int64>):>int64=>{other[0]=99 return values[0]}\nlet main=():>int64=>{let values:array<int64>=[40] return read(values @values)+2}', 42),
    ('Box:type=[values:array<int64> other:int64]\nlet read=(values:array<int64> @other:int64):>int64=>{other=99 return values[0]}\nlet main=():>int64=>{let box=Box[[42] 0] let before=_arena_cursor let answer=read(box.values @box.other) return if before =? _arena_cursor answer else 0}', 42),
    ('let shared:array<int64>=[40]\nlet read=(values:array<int64>):>int64=>{shared[0]=99 return values[0]}\nlet outer=(@values:array<int64>):>int64=>read(values)\nlet main=():>int64=>outer(@shared)+2', 42),
    ('Box:type=[n:int64]\nlet main=():>int64=>{let box=Box[40] let read=():>int64=>box.n box.n=42 return read()}', 42),
    ('let main=():>int64=>{let values:array<int64>=[40] let read=():>int64=>values[0] values[0]=42 return read()}', 42),
    ('let main=():>int64=>{let value:int64|none=42 let read=():>int64=>if value is? int64 value else 0 return read()}', 42),
    ('let add=(@n:int64):>void=>{n+=2}\nlet main=():>int64=>{let n:int64=40 add(@n); return n}', 42),
    ('let set=(@n:uint8 @yes:bool):>void=>{n=42 yes=true}\nlet main=():>int64=>{let n:uint8=0 let yes=false set(@n @yes); return if yes n as int64 else 0}', 42),
    ('let add=(@n:int64):>void=>{n+=2}\nlet forward=(@n:int64):>void=>{add(@n);}\nlet main=():>int64=>{let n:int64=40 forward(@n); return n}', 42),
    ('let add=(@n:int64):>void=>{n+=2}\nlet copy=(n:int64):>int64=>{add(@n); return n}\nlet main=():>int64=>copy(40)', 42),
    ('let add=(@n:int64):>void=>{n+=2}\nlet n:int64=40\nlet main=():>int64=>{add(@n); return n}', 42),
    ('let add=(@n:int64):>void=>{n+=2}\nlet main=():>int64=>{let box=[n=40] add(@box.n); return box.n}', 42),
    ('let add=(@n:int64):>void=>{n+=2}\nlet main=():>int64=>{let values:array<int64>=[40] add(@values[0]); return values[0]}', 42),
    ('Box:type=[n:int64]\nlet replace=(@box:Box):>void=>{box=Box[42]}\nlet main=():>int64=>{let box=Box[0] replace(@box); return box.n}', 42),
    ('Box:type=[n:int64]\nOuter:type=[box:Box]\nlet replace=(@box:Box):>void=>{box=Box[42]}\nlet main=():>int64=>{let outer=Outer[Box[0]] replace(@outer.box); return outer.box.n}', 42),
    ('Box:type=[n:int64]\nlet replace=(@box:Box):>void=>{box=Box[42]}\nlet main=():>int64=>{let boxes:array<Box>=[Box[0]] replace(@boxes[0]); return boxes[0].n}', 42),
    ('let replace=(@values:array<int64>):>void=>{values=[20 22]}\nlet main=():>int64=>{let values:array<int64>=[0] replace(@values); let sum:int64=0 loop x in values {sum+=x} return sum}', 42),
    ('let replace=(@value:int64|none):>void=>{value=42}\nlet main=():>int64=>{let value:int64|none=none replace(@value); return if value is? int64 value else 0}', 42),
    ('let main=():>int64=>{let a:set<int64>=set[1 2] let b:set<int64>=set[2 3] let result=a|b if result.length=?3 and 1 in?result and 3 in?result return 42 return 0}', 42),
    ('let main=():>int64=>{let a:set<int64>=set[1 2] let b:set<int64>=set[2 3] let result=a&b if result.length=?1 and 2 in?result return 42 return 0}', 42),
    ('let main=():>int64=>{let a:set<int64>=set[1 2] let b:set<int64>=set[2 3] let result=a-b if result.length=?1 and 1 in?result return 42 return 0}', 42),
    ('let main=():>int64=>{let a:set<int64>=set[1 2] let b:set<int64>=set[2 3] let result=a xor b if result.length=?2 and 1 in?result and 3 in?result return 42 return 0}', 42),
    ('let main=():>int64=>{let a:dict<int64 int64>=[1->20 2->99] let b:dict<int64 int64>=[2->22] let result=a|b return result[1]+result[2]}', 42),
    ('let a:dict<int64 int64>=[1->40]\nlet change=():>dict<int64 int64>=>{a[1]=99 return [2->2]}\nlet main=():>int64=>{let result=a|change() return result.get(1 0)+result.get(2 0)}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[1->20 2->22 3->99] d.pop(3); let values=d.values d[1]=99 return values[0]+values[1]}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[1->20 2->22] let keys=d.keys keys.pop(1); if 1 in? d and 1 not in? keys and 2 in? keys return 42 return 0}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[1->42] return d[1]}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[] d[1]=40 d[1]=42 return d[1]}', 42),
    ('let main=():>int64=>{let d:dict<string int64>=["answer"->42] let key:string="answer" if key in? d return d[key] return 0}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[1->42] let yes=d.get(1) let no=d.get(2) if yes isnt? none and no is? none return yes return 0}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[] return d.get(8 default=42)}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[] loop i in 0..70 {d[i]=i+1} if 41 in? d return d[41] return 0}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[1->19 2->23 3->99] d.pop(3); return d.pop(1)+d.pop(2)}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[1->7 2->20] d.pop(1); d[3]=22 let sum:int64=0 loop [k v] in d {sum+=v} return sum}', 42),
    ('let main=():>int64=>{let d:dict<int64 int64>=[1->99] d.clear d[2]=42 return d[2]}', 42),
    ('let main=():>int64=>{let s:set<int64>=set[1 2] s.add(3) s.pop(1); if 1 not in? s and 2 in? s and 3 in? s return 42 return 0}', 42),
    ('let main=():>int64=>{let d:dict<string int64>=["é"->42] let source:string="xéy" let key=source[1..2) if key in? d return d[key] return 0}', 42),
    ('Box:type=[value:int64]\nlet main=():>int64=>{let d:dict<int64 Box>=[1->Box[42]] let copy=d copy[1]=Box[0] return d[1].value}', 42),
    ('A:type=type of [text:string]\nB:type=type of [code:int64 text:string]\nlet size=(value:A|B):>int64=>value.text.length\nlet main=():>int64=>size(A["abcd"])+size(B[99 "xy"])+36', 42),
    ('A:type=type of [value:int64]\nB:type=type of [value:string]\nlet get=(value:A|B|none):>int64|string|none=>value.value\nlet main=():>int64=>{let first=get(A[40]) let second=get(B["xy"]) let absent=get(none) if first is? int64 and second is? string and absent is? none return first+second.length return 0}', 42),
    ('A:type=type of [value:int64]\nB:type=type of [other:int64 value:int64]\nlet count:int64=0\nlet next=():>A|B=>{count+=1 return B[99 40]}\nlet main=():>int64=>next().value+count+1', 42),
    ('let main=():>int64=>{let value:int64<v=>v>?0>=42 return value}', 42),
    ('let count:int64=0\nlet next=():>42=>{count+=1 return 42}\nlet main=():>int64=>{let value:int64<v=>v>?0>=next() return count+41}', 42),
    ('let choose=(value:int64|"a"|"b"):>int64=>if value is? "a" 0 else 42\nlet main=():>int64=>choose("b")', 42),
    ('let choose=(value:string):>int64=>if value is? "ok" 42 else 0\nlet main=():>int64=>choose("ok")', 42),
    ('let choose=(value:int64|"a"|"b"):>int64=>{if value is? int64 return 0 return if value is? "b" 42 else 0}\nlet main=():>int64=>choose("b")', 42),
    ('let choose=(value:string):>int64=>if value isnt? "👩\u200d👩\u200d👧\u200d👦" 42 else 0\nlet main=():>int64=>choose("👩\u200d👩\u200d👦")', 42),
    ('Box:type=[values:array<int64>]\nlet main=():>int64=>{let box=Box[[1 2]] box.values.clear box.values.push(42) return box.values[0]}', 42),
    ('Sign:type=-1|1\nlet add=(left:Sign right:Sign):>int64=>left+right\nlet main=():>int64=>add(-1 1)+42',42),
    ('Sign:type=-1|1\nlet main=():>int64=>{let value:Sign=-1 let copy=value copy=1 return if value is? -1 42 else 0}', 42),
    ('Sign:type=-1|1\nlet number=(value:Sign):>int64=>value\nlet main=():>int64=>number(-1)+43', 42),
    ('Sign:type=-1|1\nBox:type=[sign:Sign]\nlet main=():>int64=>{let value=Box[-1] return value.sign+43}', 42),
    ('Choice:type=0|"ready"|"done"\nlet main=():>int64=>{let value:Choice="done" return if value is? "done" 42 else 0}', 42),
    ('Choice:type=0|"ready"|"done"\nlet result=(flag:bool):>Choice=>if flag "ready" else 0\nlet main=():>int64=>{let value=result(true) if value is? string return if value=?"ready" 42 else 0 return 0}', 42),
    ('Sign:type=-1|1\nlet main=():>int64=>{let values:array<Sign>=[-1 1] return (values[0] as int64)+(values[1] as int64)+42}', 42),
    ('Sign:type=-1|1\nlet select=(value:-1|0|1):>Sign=>if value is? Sign value else 1\nlet main=():>int64=>(select(-1) as int64)+43', 42),
    ('Sign:type=-1|1\nlet count:int64=0\nlet next=():>1=>{count+=1 return 1}\nlet main=():>int64=>{let value:Sign=next() return count+41}', 42),


    ('let main=():>int64=>{let total:int64=0 let left:array<int64>=[20 20] let right:array<int64>=[1 1 99] loop a in left and b in right {total+=a+b} return total}', 42),
    ('let main=():>int64=>{let total:int64=0 let values:array<int64>=[20 21] loop i in 0.. and value in values {total+=i+value} return total}', 42),
    ('let main=():>int64=>{let total:int64=0 let values:array<int64>=[20 22] loop i in 0.. and i<?values.length {total+=values[i]} return total}', 42),
    ('let main=():>int64=>{let total:int64=0 let left:string="ab" let right:string="XY" loop a in left and b in right {total+=a.length+b.length} return total+38}', 42),


    ('let main=():>int64=>{let total:int64=0 loop i in 0..6 {total+=i} return total*2}', 42),
    ('let main=():>int64=>{let total:int64=0 loop i in 0,2..6 {total+=i} return total+30}', 42),
    ('let main=():>int64=>{let total:int64=0 loop i in 6,4..0 {total+=i} return total+30}', 42),
    ('let main=():>int64=>{let total:int64=0 loop i in 0..5 {if i=?2 continue total+=i} return total+29}', 42),
    ('let main=():>int64=>{let total:int64=0 loop i in 0..5 {if i=?3 break total+=i} return total+39}', 42),
    ('let main=():>int64=>{let total:int64=0 let values:array<int64>=[40 2] loop value in values {total+=value} return total}', 42),
    ('let main=():>int64=>{let total:int64=0 let values:array<int64>=[] loop value in values {total+=value} return total+42}', 42),
    ('Cell:type=[value:int64]\nlet main=():>int64=>{let total:int64=0 let values:array<Cell>=[Cell[40] Cell[2]] loop value in values {total+=value.value} return total}', 42),
    ('let main=():>int64=>{let total:int64=0 let text:string="a\\u0301👩\u200d👩\u200d👧\u200d👦" loop grapheme in text {total+=grapheme.length} return total+40}', 42),
    ('let main=():>int64=>{let values:array<int64>=[20 22 99] let selected:array<int64>=[loop value in values if value<?90 value] if selected.length<?2 return 0 return selected[0]+selected[1]}', 42),
    ('let main=():>int64=>{let values:array<int64>=[20 22] let selected:array<int64>=[loop value in values {let copy=value copy}] if selected.length<?2 return 0 return selected[0]+selected[1]}', 42),
    ('let main=():>int64=>{let values:array<int64>=[20 22] let selected:array<int64>=[loop left in values loop right in values if right>?left right] if selected.length<?1 return 0 return selected[0]+20}', 42),


    ('Box:type=[value:int64|none other:int64]\nlet main=():>int64=>{let box=Box[40 0] if box.value is? int64 {box.other=99 return box.value+2} return 0}', 42),
    ('Box:type=[value:int64|none]\nOuter:type=[box:Box]\nlet main=():>int64=>{let outer=Outer[Box[40]] if outer.box.value is? int64 return outer.box.value+2 return 0}', 42),
    ('Box:type=[value:int64|none]\nlet main=():>int64=>{let box=Box[40] if box.value is? int64 {box.value=none return if box.value is? none 42 else 0} return 0}', 42),

    ('let main=():>int64=>{let value:int64|none=40 if value isnt? none return value+2 return 0}', 42),
    ('let main=():>int64=>{let value:int64|none=none return if value is? none 42 else 0}', 42),
    ('let main=():>int64=>{let value:int64|none=40 let copy=value value=none if copy is? int64 return copy+2 return 0}', 42),
    ('let make=(value:int64):>int64|none=>value\nlet main=():>int64=>{let value=make(40) if value is? int64 return value+2 return 0}', 42),
    ('let take=(value:int64|none):>int64=>{if value is? int64 return value+2 return 0}\nlet main=():>int64=>take(40)', 42),
    ('let main=():>int64=>{let value:bool|none=true return if value is? bool and value 42 else 0}', 42),
    ('let main=():>int64=>{let value:int64|bool|none=true let copy=value value=40 return if copy is? bool and copy 42 else 0}', 42),
    ('let main=():>int64=>{let value:string|none="é" return if value is? string and value=?"é" 42 else 0}', 42),
    ('Pair:type=[x:int64 y:int64]\nlet main=():>int64=>{let value:Pair|none=Pair[40 2] let copy=value if copy is? Pair {copy.x=99} if value is? Pair return value.x+value.y return 0}', 42),
    ('Pair:type=[x:int64 y:int64]\nlet make=():>Pair|none=>Pair[40 2]\nlet main=():>int64=>{let value=make() if value is? Pair return value.x+value.y return 0}', 42),
    ('Box:type=[value:int64|none]\nlet main=():>int64=>{let box=Box[40] let copy=box copy.value=none if box.value is? int64 return box.value+2 return 0}', 42),
    ('let main=():>int64=>{let values:array<int64|none>=[40 none] let copy=values copy[0]=none let value=values[0] if value is? int64 return value+2 return 0}', 42),
    ('let narrow=(value:bool):>int64|none=>if value 40 else none\nlet main=():>int64=>{let value:int64|bool|none=narrow(true) if value is? int64 return value+2 return 0}', 42),

    ('let main=():>int64=>{let text:string="héllo" return text.length+37}', 42),
    ('let main=():>int64=>{let text:string="a\\u0301👩\u200d👩\u200d👧\u200d👦Z" return text.length+39}', 42),
    ('let main=():>int64=>{let a:string="hello" let b:string="hello" return if a=?b 42 else 0}', 42),
    ('let main=():>int64=>{let a:string="hello" let b:string="jello" return if a not=?b 42 else 0}', 42),
    ('let main=():>int64=>{let a:string="" let b:string="x" return if a not=?b 42 else 0}', 42),
    ('let main=():>int64=>{let text:string="a\\u0301b" let g=text[0] return if g=?"a\\u0301" 42 else 0}', 42),
    ('let main=():>int64=>{let text:string="AéBCD" let part=text[1..4) let nested=part[1..] return if nested=?"BC" 42 else 0}', 42),
    ('let main=():>int64=>{let text:string="abc" let empty=text[2..1] return if empty=?"" 42 else 0}', 42),
    ('let main=():>int64=>{let text:string="*" let bytes=text as array<uint8> return bytes[0] as int64}', 42),
    ('let main=():>int64=>{let text:string="*" let bytes=text as array<uint8> bytes[0]=99 return if text=?"*" 42 else 0}', 42),
    ('let tail=(text:string):>string=>if text.length>?1 text[1..] else ""\nlet main=():>int64=>{let text=tail("aé") return if text=?"é" 42 else 0}', 42),
    ('let main=():>int64=>{let values:array<string>=["a" "é"] let copy=values copy[0]="z" return if values[0]=?"a" and copy[1]=?"é" 42 else 0}', 42),
    ('Box:type=[text:string]\nlet make=():>Box=>Box["é"]\nlet main=():>int64=>{let box=make() let copy=box copy.text="z" return if box.text=?"é" 42 else 0}', 42),
    ('let make=():>array<string>=>["a" "é"]\nlet main=():>int64=>{let values=make() if values.length<?2 return 0 return if values[1]=?"é" 42 else 0}', 42),

    ('Cell:type=[value:int64]\nlet main=():>int64=>{let item=Cell[40] let values:array<Cell>=[item] let copy=values copy[0].value=99 return item.value+values[0].value-38}', 42),
    ('let main=():>int64=>{let inner:array<int64>=[40 2] let rows:array<array<int64 length=2>>=[inner] let copy=rows copy[0][0]=99 return rows[0][0]+copy[0][1]}', 42),
    ('Cell:type=[value:int64]\nlet main=():>int64=>{let item=Cell[40] let values:array<Cell>=[] values.push(item) item.value=99 values.reserve(100) let removed=values.pop return removed.value+2}', 42),
    ('let main=():>int64=>{let inner:array<int64>=[40 2] let rows:array<array<int64 length=2>>=[[0 0]] rows[0]=inner inner[0]=99 return rows[0][0]+rows[0][1]}', 42),
    ('Node:type=$abstract type of [value:int64]\nLeaf:type=type of Node\nBranch:type=type of Node & [children:array<Node>]\nlet main=():>int64=>{let root:Node=Branch[40 [Leaf[2]]] let copy=root if copy is? Branch and copy.children.length >? 0 {copy.children[0]=Leaf[99]} if root is? Branch and root.children.length >? 0 return root.value+root.children[0].value return 0}', 42),
    ('Fn:type=(x:int64):>int64\nlet twice=(x:int64):>int64=>x*2\nlet main=():>int64=>{let values:array<Fn>=[@twice] let copy=values return copy[0](21)}', 42),
    ('Pair:type=[x:int64 y:int64]\nlet make=():>Pair=>Pair[40 2]\nlet main=():>int64=>{let value=make() return value.x+value.y}', 42),
    ('Pair:type=[x:int64 y:int64]\nlet change=(value:Pair):>int64=>{value.x=99 return value.y}\nlet main=():>int64=>{let value=Pair[40 2] return change(value)+value.x}', 42),
    ('Box:type=[values:array<int64>]\nlet make=():>Box=>Box[[40 2]]\nlet main=():>int64=>{let value=make() let copy=value copy.values[0]=99 return value.values[0]+copy.values[1]}', 42),
    ('Base:type=type of [x:int64]\nChild:type=type of Base & [values:array<int64>]\nlet make=():>Base=>Child[40 [2]]\nlet main=():>int64=>{let value=make() let copy=value if copy is? Child return copy.x+copy.values[0] return 0}', 42),

    ('let main=():>int64=>{let values:array<int64>=[] values.push(40) values.push(2) return values.pop+values.pop}', 42),
    ('let main=():>int64=>{let values:array<int64>=[20 9] values.reserve(12) values.insert(22 1) values.pop(idx=2); return values[0]+values[1]}', 42),
    ('let main=():>int64=>{let values:array<int64>=[40 2 9] values.truncate(2) values.truncate(100) let answer=values[0]+values[1] values.clear; values.push(answer) return values.pop}', 42),
    ('let main=():>int64=>{let values:array<uint8>=[40 2] values.insert(idx=1 value=99) values.pop(1); return (values[0]+values[1]) as int64}', 42),
    ('let main=():>int64=>{let values:array<bool>=[] values.push(true) values.insert(false 0) let first=values.pop(0) let last=values.pop return if not first and last 42 else 0}', 42),
    ('let change=(values:array<int64>):>int64=>{values[0]=99 return values[1]}\nlet main=():>int64=>{let values:array<int64>=[40 2] return change(values)+values[0]}', 42),
    ('let make=():>array<int64>=>[40 2]\nlet main=():>int64=>{let values=make() return values[0]+values[1]}', 42),
    ('let identity=(values:array<int64>):>array<int64>=>values\nlet main=():>int64=>{let values:array<int64>=[40 2] let copy=identity(values) copy[0]=99 return values[0]+copy[1]}', 42),
    ('let values:array<int64>=[40 2]\nlet main=():>int64=>{let copy=values copy[0]=99 return values[0]+copy[1]}', 42),
    ('let values:array<int64>=[40 2]\nlet mutate=():>int64=>{values[0]=99 return 2}\nlet choose=(left:array<int64> right:int64):>int64=>left[0]+right\nlet main=():>int64=>choose(values mutate())', 42),
    ('let values:array<int64>=[40 2]\nlet choose=(copy:array<int64>=values):>int64=>{copy[0]=99 return copy[1]}\nlet main=():>int64=>choose()+values[0]', 42),
    ('let make=():>array<bool>=>[false true]\nlet main=():>int64=>{let values=make() return if values[1] and not values[0] 42 else 0}', 42),
]


# Replacing a field or an ancestor invalidates its narrowed read type.
REJECTED_CASES = ['Box:type=[value:int64|none]\nlet main=():>int64=>{let box=Box[40] if box.value is? int64 {box.value=none return box.value+2} return 0}', 'Box:type=[value:int64|none]\nlet main=():>int64=>{let box=Box[40] if box.value is? int64 {box=Box[none] return box.value+2} return 0}', 'Box:type=[value:int64|none]\nOuter:type=[box:Box]\nlet main=():>int64=>{let outer=Outer[Box[40]] if outer.box.value is? int64 {outer.box=Box[none] return outer.box.value+2} return 0}']

def test_native_scalar_lowering(tmp_path):
    source = tmp_path / 'lowering.dewy'
    source.write_text(f'''
from reporting import SrcFile, Error
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/check.dewy'}" as checking
import p"{ROOT / 'dewy/bootstrap/backend/udewy/emit.dewy'}" as emit
import p"{ROOT / 'dewy/bootstrap/backend/udewy/layouts.dewy'}" as layouts
import p"{ROOT / 'dewy/bootstrap/backend/udewy/lower.dewy'}" as lower
import p"{ROOT / 'dewy/bootstrap/backend/udewy/program.dewy'}" as program
main = (argv:array<string>):>int64 => {{
    $runtime_assert argv.length =? 2
    let text=p(argv[1]).read_text
    if text isnt? string return 1
    let source=SrcFile[argv[1] text]
    let parsed=parser.parse(source)
    if parsed is? Error {{parsed.fail}}
    let session=contexts.Session[]
    let lexical=contexts.begin(source parsed.nodes @session)
    let env=checking.begin(lexical @session)
    let root=checking.module(parsed.root env @session)
    if root is? Error {{root.fail}}
    let allocator=bindings.lookup(session.scopes env.lexical.scope '_arena_alloc')
    let helpers:dict<string addr>=[]
    let release=bindings.lookup(session.scopes env.lexical.scope '_arena_release')
    if release isnt? none {{helpers['_arena_release']=release}}
    let lowered=lower.lower(root emit.Input[session.hir session.types] source allocator=allocator layout_context=layouts.Context[session.brands] runtime_helpers=helpers)
    if lowered is? Error {{lowered.fail}}
    let code=program.render(lowered.program lowered.input)
    if code is? Error {{code.fail}}
    printl(code)
    return 0
}}
''')
    seed = source.with_suffix('.udewy')
    seed.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    binary = cache_artifact(seed).resolve()
    for index, (text, expected_exit) in enumerate(CASES + [(ARENA + text, code) for text, code in ARENA_CASES]):
        case = tmp_path / f'case-{index}.dewy'
        case.write_text(text)
        native = subprocess.run([binary, case], capture_output=True, text=True, timeout=60, check=False)
        assert native.returncode == 0, native.stdout + native.stderr
        output = case.with_suffix('.udewy')
        output.write_text(native.stdout)
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], timeout=10, check=False)
        assert result.returncode == expected_exit, text

    for index,text in enumerate(REJECTED_CASES):
        case=tmp_path/f'rejected-{index}.dewy'
        case.write_text(text)
        native=subprocess.run([binary,case],capture_output=True,text=True,timeout=60,check=False)
        assert native.returncode!=0,text
        assert 'no overload takes' in native.stderr,native.stdout+native.stderr

    # This driver deliberately stops below full bounds analysis. Unknown or
    # refuted promises must survive checking and prevent unchecked lowering.
    for index, text in enumerate([
        'let f=(x:int64):>int64<v=>v>?0>=>x',
        'let main=():>int64=>{let value:int64<v=>v>?0>=-1 return value}',
    ]):
        case = tmp_path / f'unresolved-{index}.dewy'
        case.write_text(text)
        native = subprocess.run([binary, case], capture_output=True, text=True, timeout=60, check=False)
        assert native.returncode != 0, text
        assert 'Obligation legalization' in native.stderr, native.stdout + native.stderr

    for index, text in enumerate([
        'let main=():>int64=>{let n:int64=40 let write=():>void=>{n=42} write(); return n}',
        'Fn:type=():>int64\nlet take=(f:Fn):>int64=>f()\nlet main=():>int64=>{let n:int64=42 let read=():>int64=>n return take(@read)}',
        'let main=():>int64=>{let values:array<int64>=[40] let write=():>void=>{values[0]=42} write(); return values[0]}',
    ]):
        case = tmp_path / f'closure-storage-{index}.dewy'
        case.write_text(ARENA + text)
        native = subprocess.run([binary, case], capture_output=True, text=True, timeout=60, check=False)
        assert native.returncode != 0, text
        assert 'closure storage' in native.stderr, native.stdout + native.stderr
