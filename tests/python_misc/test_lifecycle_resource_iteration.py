"""Iterator snapshots use ordinary owners; iteration values borrow or copy."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HEADER='''let drops:int64=0
let copies:int64=0
Handle=type of [id:int64
$__drop__ release=():>void=>{drops+=id}
$__copy__ clone=():>Handle=>{copies+=1 Handle[id]}
]
'''
CASES=[HEADER+'''work=():>int64=>{let xs:array<Handle>=[Handle[20] Handle[22]]
 let sum:int64=0 loop x in xs {sum+=x.id}
 if sum not=?42 or copies not=?0 return 1
 if xs.length not=?2 return 2 return 42}
main=():>int64=>{if work() not=?42 or drops not=?42 return 1 return 42}''',
HEADER+'''work=():>int64=>{let xs:array<Handle>=[Handle[20] Handle[22]]
 let sum:int64=0 loop x in xs {xs.clear sum+=x.id}
 if sum not=?42 or copies not=?2 return 1 return 42}
main=():>int64=>{if work() not=?42 or drops not=?84 return 1 return 42}''',
HEADER+'''work=():>int64=>{let xs:array<Handle>=[Handle[20] Handle[22]]
 let sum:int64=0 loop x in xs {let y=x y.id+=1 sum+=y.id}
 if sum not=?44 or copies not=?2 return 1
 if xs.length=?2 {if xs[0].id not=?20 return 2} return 42}
main=():>int64=>{if work() not=?42 or drops not=?86 return 1 return 42}''',
HEADER+'''make=():>array<Handle>=>[Handle[20] Handle[22]]
work=():>int64=>{loop x in make() {return x.id+22} return 1}
main=():>int64=>{if work() not=?42 or drops not=?42 return 1 return 42}''',
HEADER+'''work=():>int64=>{let d:dict<int64 Handle>=[1->Handle[20] 2->Handle[22]]
 let sum:int64=0 loop [k v] in d {sum+=v.id}
 if copies not=?0 or sum not=?42 return 1 return 42}
main=():>int64=>{if work() not=?42 or drops not=?42 return 1 return 42}''',
]

CASES += [HEADER+'''let calls:int64=0
make=():>dict<int64 Handle>=>{calls+=1 [1->Handle[20] 2->Handle[22]]}
work=():>int64=>{let sum:int64=0 loop [k v] in make() {sum+=v.id} return sum}
main=():>int64=>{if work() not=?42 or drops not=?42 or calls not=?1 return 1 return 42}''',
'''let drops:int64=0
Handle=type of [id:int64 $__drop__ release=():>void=>{drops+=id}]
sum=(@xs:array<Handle>):>int64=>{let result:int64=0 loop x in xs {result+=x.id} return result}
work=():>int64=>{let xs:array<Handle>=[Handle[20] Handle[22]] return sum(@xs)}
main=():>int64=>{if work() not=?42 or drops not=?42 return 1 return 42}''']

CASES += [HEADER+'''make=():>array<Handle>=>[Handle[20] Handle[22]]
work=():>int64=>{let n:int64=0 loop x in make() {if x.id=?20 continue n+=x.id break} return n+20}
main=():>int64=>{if work() not=?42 or drops not=?42 return 1 return 42}''',
HEADER+'''let calls:int64=0
make=():>array<Handle>=>{calls+=1 [Handle[20] Handle[22]]}
work=():>int64=>{if true {return 42} else {loop x in make() {return 1}} return 2}
main=():>int64=>{if work() not=?42 or drops not=?0 or calls not=?0 return 1 return 42}''',
HEADER+'''make=():>array<Handle length=2>=>[Handle[20] Handle[22]]
work=():>int64=>{let sum:int64=0 loop x in make() or i in [0..3) {if x isnt? none {sum+=x.id}} return sum}
main=():>int64=>{if work() not=?42 or drops not=?42 return 1 return 42}''',
HEADER+'''work=():>int64=>{let d:dict<int64 Handle>=[1->Handle[20] 2->Handle[22]]
 let sum:int64=0 loop [k v] in d {d.clear sum+=v.id}
 if copies not=?2 or sum not=?42 return 1 return 42}
main=():>int64=>{if work() not=?42 or drops not=?84 return 1 return 42}''']

ERRORS = [CASES.pop(), CASES[0].replace('sum+=x.id', 'x.id+=1'),
    CASES[6].replace('result+=x.id', 'xs.clear result+=x.id'),
    CASES[0].replace('work=():>int64=>', 'work=():>int64 & no_effects=>')]

# Returning from the loop and advancing its backedge both reclaim owners.
CASES.append(CASES[3].replace(
    'if work() not=?42 or drops not=?42 return 1 return 42',
    'if work() not=?42 or drops not=?42 return 1 let before:int64=_arena_live_bytes '
    'loop i in 0.. and i<?100 {if work() not=?42 return 2} '
    '$runtime_assert _arena_live_bytes=?before return 42'))

CASES.append(HEADER+'''let order:int64=0
left=():>array<int64>=>{order=order*10+1 [0 0]}
right=():>array<Handle>=>{order=order*10+2 [Handle[20] Handle[22]]}
work=():>int64=>{let sum:int64=0 loop i in left() and x in right() {sum+=i+x.id} return sum}
main=():>int64=>{if work() not=?42 or order not=?12 or drops not=?42 return 1 return 42}''')

@pytest.mark.parametrize('source', CASES)
def test_resource_iteration(tmp_path, source):
    execute(tmp_path, 'iteration', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_resource_iteration_obligations(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_resource_iteration(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
