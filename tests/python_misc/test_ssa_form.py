"""The optimizing route builds each function in SSA form and writes it back
as expression trees (dewy/bootstrap/OPTIMIZER.md).

These programs pin what the form must preserve: a name bound to a variable
keeps the value it saw, values do not move past the assignments and calls
that would change them, lazy conditions stay lazy, a small function built in
place of its call behaves as the call did, and an operation is reused only
where its earlier result still stands."""
from test_bootstrap_structural_text import build_program_driver, check_structural_text

CASES = [
    # A name bound once keeps the variable's value at that point.
    '''main=():>int64=>{
    let x:int64=5
    let before=x
    x=x+1
    let between=x
    x=x*2
    return if before=?5 and between=?6 and x=?12 42 else 1
}''',
    # A swap through a saved value, repeated in a loop.
    '''main=():>int64=>{
    let a:int64=0
    let b:int64=1
    let i:int64=0
    loop i <? 10 {
        let next=a+b
        a=b
        b=next
        i+=1
    }
    return if a=?55 and b=?89 42 else 1
}''',
    # A value computed before a conditional assignment keeps the old value.
    '''pick=(flag:bool):>int64=>{
    let x:int64=10
    let y=x+1
    if flag {x=100}
    return y+x
}
main=():>int64=>if pick(true)=?111 and pick(false)=?21 42 else 1''',
    # Breaks and continues carry each variable's value out of the loop.
    '''main=():>int64=>{
    let total:int64=0
    let found:int64=-1
    let i:int64=0
    loop i <? 100 {
        i+=1
        if i%2 =? 0 continue
        total+=i
        if total >? 30 {found=i break}
    }
    return if found=?11 and total=?36 and i=?11 42 else 1
}''',
    # Nested loops: the inner loop's variables do not disturb the outer's.
    '''main=():>int64=>{
    let total:int64=0
    let i:int64=0
    loop i <? 4 {
        let j:int64=0
        let row:int64=0
        loop j <? 4 {
            if j =? i {j+=1 continue}
            row+=j
            j+=1
        }
        total+=row*i
        i+=1
    }
    return if total=?22 42 else total
}''',
    # Lazy conditions: the right side runs only when reached, in order.
    '''let calls:int64=0
touch=(result:bool):>bool=>{calls+=1 return result}
main=():>int64=>{
    let reached:int64=0
    if touch(false) and touch(true) {reached+=1}
    if touch(true) or touch(false) {reached+=10}
    if touch(true) and (touch(false) or touch(true)) {reached+=100}
    return if reached=?110 and calls=?5 42 else calls
}''',
    # A global read before a call that changes it keeps the earlier value.
    '''let counter:int64=1
bump=():>void=>{counter+=1}
main=():>int64=>{
    let before=counter
    bump()
    let after=counter
    bump()
    return if before=?1 and after=?2 and counter=?3 42 else 1
}''',
    # A small function with early returns, built in place several times.
    '''clamp=(value:int64 low:int64 high:int64):>int64=>{
    if value <? low return low
    if value >? high return high
    return value
}
main=():>int64=>{
    let total:int64=0
    let i:int64=-5
    loop i <? 15 {
        total+=clamp(i 0 9)
        i+=1
    }
    return if total=?90 and clamp(clamp(50 0 20) 5 10)=?10 42 else total
}''',
    # A small function that changes its own parameter and loops.
    '''digits=(value:int64):>int64=>{
    let count:int64=1
    loop value >=? 10 {
        value=value//10
        count+=1
    }
    return count
}
main=():>int64=>{
    let number:int64=12345
    let total=digits(number)+digits(7)+digits(number*100)
    return if total=?13 and number=?12345 42 else total
}''',
    # A constant argument decides the callee's test where it is built.
    '''choose=(first:bool a:int64 b:int64):>int64=>if first a else b
main=():>int64=>if choose(true 40 1)+choose(false 1 2)=?42 42 else 1''',
    # Arguments are evaluated once, in order, before the body runs.
    '''let trace:int64=0
step=(digit:int64):>int64=>{trace=trace*10+digit return digit}
add=(a:int64 b:int64):>int64=>a+b
main=():>int64=>{
    let sum=add(step(1) add(step(2) step(3)))
    return if sum=?6 and trace=?123 42 else trace
}''',
    # A value read through an index keeps the index it was computed with,
    # even when its only use comes after the index changes and after a loop.
    '''bump=(n:int64 depth:int64):>int64=>if depth =? 0 n else bump(n+1 depth-1)
work=():>int64=>{
    let items=[40 2]
    let index:int64=0
    let slot=items[index]
    index=1
    let later=bump(slot 2)
    let total:int64=0
    loop v in items {total+=v}
    return later+total-index
}
main=():>int64=>if work()=?83 42 else 1''',
    # Division by a constant is done by multiplying or shifting: it agrees
    # with division by the same number met only when the program runs.
    '''main=():>int64=>{
    let values:array<int64>=[0 1 (-1) 7 (-7) 1000000007 (-1000000007) 9223372036854775807 (0-9223372036854775807-1) 4611686018427387904 123456789012345 (-123456789012345)]
    let divisors:array<int64>=[2 3 7 8 10 1000 4096 1000000007 2147483647 2147483648 4611686018427387904]
    let bad:int64=0
    loop x in values {
        let quotients:array<int64>=[x//2 x//3 x//7 x//8 x//10 x//1000 x//4096 x//1000000007 x//2147483647 x//2147483648 x//4611686018427387904]
        let remainders:array<int64>=[x%2 x%3 x%7 x%8 x%10 x%1000 x%4096 x%1000000007 x%2147483647 x%2147483648 x%4611686018427387904]
        loop i in 0.. and i <? divisors.length and i <? quotients.length and i <? remainders.length {
            let d=divisors[i]
            if d >? 0 and (x//d not=? quotients[i] or x%d not=? remainders[i]) {bad+=1}
        }
    }
    return if bad=?0 42 else bad
}''',
    # A value read from storage is read again after a store, a call or a
    # loop round that may have changed it.
    '''bump=(@cells:array<int64>):>void=>{if cells.length >? 0 {cells[0]=cells[0]+1}}
main=():>int64=>{
    let cells:array<int64>=[5 7]
    let first=cells[0]+cells[1]
    cells[0]=20
    let second=cells[0]+cells[1]
    bump(@cells)
    if cells.length <? 2 return 1
    let third=cells[0]+cells[1]
    let i:int64=0
    let seen:int64=0
    loop i <? 3 {
        seen+=cells[1]
        cells[1]=cells[1]+1
        i+=1
    }
    return if first=?12 and second=?27 and third=?28 and seen=?24 42 else 1
}''',
    # An operation computed once is reused only where that computation
    # always ran: not from the lazy side of a test, nor from another arm.
    '''pick=(a:int64 b:int64 flag:bool):>int64=>{
    let result:int64=0
    if flag or a*b >? 100 {result=a*b}
    if flag {result+=a*b+1} else {result+=a*b+2}
    return result+a*b
}
main=():>int64=>if pick(3 4 true)=?37 and pick(3 4 false)=?26 and pick(20 30 false)=?1802 42 else 1''',
]


def test_ssa_form(tmp_path):
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
