"""A small literal bound to a runtime-length local starts in frame slots.

The worklist may still grow: past its frame slots the data moves to the
arena and the frame descriptor becomes its sole owner. A copy of that
descriptor (a callee keeping a lent place, an explicit copy) must then copy
the storage rather than share a descriptor that dies with the frame."""
from test_scalar_projection import execute
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile

CASES = [
    # A lent place grows past its frame slots, then the callee keeps a copy.
    '''Block:type=[items:array<int64>]
finish=(value:int64 @prefix:array<int64>):>Block=>{
    prefix.push(value)
    return Block[prefix]
}
build=(x:int64 count:int64):>Block=>{
    let prefix:array<int64>=[]
    let i:int64=0
    loop i <? count {prefix.push(x) i+=1}
    return finish(x+1 @prefix)
}
smash=(n:int64):>int64=>{
    let junk:array<int64>=[n n n n n n n n n n n n n n n n]
    return junk[0]+junk[15]
}
sum=(block:Block):>int64=>{
    let total:int64=0
    loop v in block.items {total+=v}
    return total
}
main=():>int64=>{
    let small=build(1 3)
    smash(100);
    let large=build(2 40)
    smash(100);
    return if sum(small)=?5 and sum(large)=?83 42 else 1
}''',
    # An explicit copy after growth stays independent of the worklist.
    '''main=():>int64=>{
    let items:array<int64>=[1 2]
    let i:int64=0
    loop i <? 30 {items.push(i) i+=1}
    let kept=items.copy
    items[0]=100
    items.push(7)
    return if kept[0]=?1 and kept.length=?32 and items.length=?33 42 else 1
}''',
    # Iteration and method receivers only; growth and shrinking in a loop.
    '''main=():>int64=>{
    let work:array<int64>=[5]
    let seen:int64=0
    loop work.length >? 0 {
        let n=work.pop
        seen+=1
        if n >? 0 {work.push(n-1) work.push(n-1)}
    }
    let total:int64=0
    let rest:array<int64>=[1 2 3]
    loop v in rest {total+=v}
    return if seen=?63 and total=?6 42 else 1
}''',
    # A captured worklist stays ordinary storage.
    '''main=():>int64=>{
    let items:array<int64>=[1 2 3]
    let count=()=>items.length
    items.push(4)
    return if count()=?4 42 else 1
}''',
]


def test_frame_worklists(tmp_path):
    for index, source in enumerate(CASES):
        execute(tmp_path, f'frame-worklists-{index}', codegen(SrcFile(None, source), debug_locations=False))


def test_native_frame_worklists(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
