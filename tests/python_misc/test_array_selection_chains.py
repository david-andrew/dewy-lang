"""Selection loans remain rooted across blocks and other selected views."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CHAIN = '''$explicit_copies
work=(xs:array<int64> flag:bool):>int64 & no_effects=>{
 const first:array<int64>=if flag xs else {if flag [42] else []}
 const second:array<int64>=if flag first else [42]
 return if second.length>?0 second[0] else 1
}
main=():>int64=>{
 let xs:array<int64>=[42]
 if work(xs true) not=?42 or work(xs false) not=?42 return 1
 let before:int64=_arena_allocated_bytes
 loop i in [0..1000) {if work(xs true) not=?42 return 2}
 return if _arena_allocated_bytes=?before 42 else 3
}'''
CASES = [CHAIN,
 CHAIN.replace('const second:', 'const middle:array<int64>=if flag first else [42]\n const second:').replace('if flag first else [42]\n return', 'if flag middle else [42]\n return'),
 CHAIN.replace('if flag first else [42]', 'if flag {if flag first else []} else [42]'),
 CHAIN.replace('const second:', 'const another:array<int64>=if flag xs else [42]\n const second:').replace('if flag first else [42]', 'if flag first else another'),
 # Ownership fallback keeps both snapshots independent after root mutation.
 CHAIN.replace('$explicit_copies\n','').replace(' & no_effects','').replace(' return if second.length',' xs.clear()\n return if second.length').replace(' let before:int64=_arena_allocated_bytes',' let before:int64=_arena_allocated_bytes').split('main=')[0]+'main=():>int64=>work([42] true)',
]
CASES.append("""$explicit_copies
Box:type=[items:array<int64>]
let counter:int64=0
tick=():>void=>{counter+=1}
make=():>Box=>Box[[42]]
work=(flag:bool):>int64=>{
 let owner=if flag {make()} else none
 const selected:array<int64>=if owner is? Box owner.items else [42]
 tick()
 return if selected.length>?0 selected[0] else 1
}
main=():>int64=>if work(true)=?42 and work(false)=?42 and counter=?2 42 else 1""")

ERRORS = [
 CHAIN.replace(' return if second.length',' xs.clear()\n return if second.length'),
 CHAIN.replace(' return if second.length',' second.clear()\n return if second.length'),
 CHAIN.replace(' return if second.length',' let owned=second\n owned.clear()\n return if second.length'),
 CHAIN.replace(':>int64 & no_effects=>{', ':>array<int64>=>{',1).split('main=')[0].replace('return if second.length>?0 second[0] else 1','return second'),
]

# Moving an apparent last-use owner must account for both dependent views.
RETAINED = """make=():>array<int64>=>[42]
work=(flag:bool):>int64=>{
 let owner=make()
 const first:array<int64>=if flag owner else []
 const second:array<int64>=if flag first else []
 let changed=owner
 changed.clear()
 return if second.length>?0 second[0] else 1
}
main=():>int64=>work(true)"""
CASES.append(RETAINED)
ERRORS.append('$explicit_copies\n'+RETAINED)

@pytest.mark.parametrize('source', CASES)
def test_array_selection_chain(tmp_path, source):
    execute(tmp_path,'selected-chain',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_array_selection_chain_keeps_copy_obligations(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source),debug_locations=False)


def test_native_array_selection_chains(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
