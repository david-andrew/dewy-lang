"""Later conditional guards run only when all earlier arms were skipped."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
Box:type=[items:array<int64>]
Holder:type=[item:Box|none]
make=(present:bool):>Box|none=>if present Box[[42]] else none
choose=(which:int64 present:bool):>Holder=>{
    let value=make(present)
    let result=Holder[none]
    if which=?0 {result=Holder[value]}
    else if value is? Box and which=?1 {result=Holder[value]}
    else if value is? Box and value.items.length>?0 {result=Holder[value]}
    else {result=Holder[value]}
    return result
}
work=(which:int64 present:bool):>int64=>{
    let result=choose(which present)
    if result.item is? none return if present 1 else 42
    return if result.item.items.length>?0 result.item.items[0] else 2
}
main=():>int64=>{
    if work(0 true) not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in [0..100) {
        loop which in [0..3) {
            if work(which true) not=?42 or work(which false) not=?42 return 2
        }
    }
    return if _arena_live_bytes=?before 42 else 3
}
'''
CASES = [SOURCE,
    SOURCE.replace('if which=?0 {result=Holder[value]}',
        'if which=?0 {if present {result=Holder[value]} else {result=Holder[value]}}'),
]
ERRORS = [SOURCE.replace('return result\n}', 'if value is? Box and value.items.length=?0 return Holder[none]\n    return result\n}', 1)]


@pytest.mark.parametrize('source', CASES)
def test_ordered_guards_do_not_keep_taken_arm_values_live(tmp_path, source):
    execute(tmp_path, 'ordered-guard-moves', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_reads_after_the_join_keep_the_value_live(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_ordered_guard_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
