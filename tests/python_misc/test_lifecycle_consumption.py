"""One last-use rule supplies owners to calls and aggregate construction."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

RESOURCE='''let drops:int64=0
Handle=type of [value:int64
$__drop__
release=():>void=>{drops+=1}
]
'''
CASES=[
    RESOURCE+'''consume=(h:Handle):>int64=>h.value
probe=():>void=>{loop i in [0..3) {let h=Handle[42]
if i=?2 break
consume(h);}}
main=():>int64=>{probe() return if drops=?3 42 else 0}''',
    RESOURCE+'''consume=(h:Handle):>int64=>h.value
main=():>int64=>{let before:int64=_arena_live_bytes
loop i in [0..100) {let h=Handle[42] consume(h);}
$runtime_assert _arena_live_bytes=?before
return if drops=?100 42 else 0}''',
    '''let drops:int64=0 let moves:int64=0
Moving=type of [value:int64 values:array<int64>
$__drop__
release=():>void=>{drops+=1 values.clear}
$__move__
relocate=():>Moving=>{moves+=1 Moving[value+1 values.copy()]}
]
consume=(h:Moving):>int64=>h.value
main=():>int64=>{let h=Moving[41 [1 2]] let answer=consume(h)
return if moves=?1 and drops=?1 answer else 0}''',
    '''let moves:int64=0
Moving=type of [value:int64
$__drop__
release=():>void=>{}
$__move__
relocate=():>Moving=>{moves+=1 Moving[value+1]}
]
main=():>int64=>{let owner=Moving[21] let view=owner let other=owner
return if moves=?0 view.value+other.value else 0}''',
    RESOURCE+'''consume=(h:Handle|none):>int64=>if h is? none 0 else h.value
main=():>int64=>{let h:Handle|none=Handle[42] let answer=consume(h)
return if drops=?1 answer else 0}''',
    RESOURCE+'''Box:type=[item:Handle]
probe=():>int64=>{let box=Box[Handle[1]] let h=Handle[42] box.item=h return box.item.value}
main=():>int64=>{let answer=probe() return if drops=?2 answer else 0}''',
    RESOURCE+'''probe=():>int64=>{let xs:array<Handle>=[Handle[1]] let h=Handle[42] xs[0]=h return xs[0].value}
main=():>int64=>{let answer=probe() return if drops=?2 answer else 0}''',
    RESOURCE+'''consume=(h:Handle):>int64=>h.value
main=():>int64=>{let h=Handle[42] let answer=consume(h)
return if drops=?1 answer else 0}''',
    RESOURCE+'''consume=(h:Handle):>int64=>h.value
forward=(h:Handle):>int64=>consume(h)
main=():>int64=>{let h=Handle[42] let answer=forward(h)
return if drops=?1 answer else 0}''',
    RESOURCE+'''Box:type=[item:Handle]
probe=():>int64=>{let h=Handle[42] let box=Box[h] return box.item.value}
main=():>int64=>{let answer=probe() return if drops=?1 answer else 0}''',
    RESOURCE+'''probe=():>int64=>{let h=Handle[42] let xs:array<Handle>=[h] return xs[0].value}
main=():>int64=>{let answer=probe() return if drops=?1 answer else 0}''',
    RESOURCE+'''probe=():>int64=>{let h=Handle[42] let xs:array<Handle>=[] xs.push(h) return xs[0].value}
main=():>int64=>{let answer=probe() return if drops=?1 answer else 0}''',
]
ERRORS=[
    RESOURCE+'''consume=(a:Handle b:Handle):>int64=>a.value+b.value
main=():>int64=>{let h=Handle[21] return consume(h h)}''',
    RESOURCE+'''consume=(h:Handle):>int64=>h.value
main=():>int64=>{let h=Handle[42] loop i in [0..2) {consume(h);} return 42}''',
    RESOURCE+'''consume=(h:Handle):>int64=>h.value
bad=():>int64 & no_effects=>{let h=Handle[42] return consume(h)}''',
    RESOURCE+'''consume=(h:Handle):>int64=>h.value
main=():>int64=>{let h=Handle[42] let view=h let derived=view consume(h); return derived.value}''',
    RESOURCE+'''consume=(h:Handle):>int64=>h.value
main=():>int64=>{let h=Handle[42] consume(h); return h.value}''',
    RESOURCE+'''consume=(h:Handle):>int64=>h.value
main=():>int64=>{let h=Handle[42] let view=h consume(h); return view.value}''',
]
@pytest.mark.parametrize('source',CASES)
def test_last_use_resource_input(tmp_path,source):
    execute(tmp_path,'consumption',codegen(SrcFile(None,source),debug_locations=False))
@pytest.mark.parametrize('source',ERRORS)
def test_live_resource_input_rejected(source):
    with pytest.raises(ReportException): codegen(SrcFile(None,source))

def test_resource_consumption_kernel(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_consumption.dewy'
    execute(tmp_path, 'consumption-kernel', codegen(SrcFile.from_path(source), debug_locations=False))


def test_native_resource_consumption(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES+[(Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_consumption.dewy').read_text()],errors=ERRORS)
