"""A union type test over branded records checks merged brand ranges.

Each brand and its descendants form one numbered range. `is? A|B|C` merges
the members' ranges, so adjacent siblings and whole families cost one
comparison, and members that never match the tested value drop out."""
from test_scalar_projection import execute
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile

SOURCE = '''Node:type=$abstract type of [id:int64]
Leaf:type=type of Node & [a:int64]
Pair:type=type of Node & [b:int64]
Group:type=$abstract type of Node & [width:int64]
Seq:type=type of Group & [c:int64]
Alt:type=type of Group & [d:int64]
Other:type=type of Node & [e:int64]
classify=(n:Node):>int64=>{
    if n is? Leaf|Other return 1
    if n is? Pair|Group return 2
    return 3
}
outside=(n:Node):>int64=>if n isnt? Leaf|Pair|Seq 10 else 0
family=(n:Node):>int64=>if n is? Alt|Seq 100 else 0
build=(i:int64):>Node=>{
    if i%5 =? 0 return Leaf[id=i a=1]
    if i%5 =? 1 return Pair[id=i b=2]
    if i%5 =? 2 return Seq[id=i width=1 c=3]
    if i%5 =? 3 return Alt[id=i width=1 d=4]
    return Other[id=i e=5]
}
main=():>int64=>{
    let total:int64=0
    let i:int64=0
    loop i <? 10 {
        let n=build(i)
        total+=classify(n)+outside(n)+family(n)
        i+=1
    }
    # Per five: classify 1+2+2+2+1, outside 0+0+0+10+10, family 0+0+100+100+0.
    return if total =? 2*(8+20+200) 42 else 1
}
'''


def test_brand_range_tests(tmp_path):
    execute(tmp_path, 'brand-ranges', codegen(SrcFile(None, SOURCE), debug_locations=False))


def test_native_brand_range_tests(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])
