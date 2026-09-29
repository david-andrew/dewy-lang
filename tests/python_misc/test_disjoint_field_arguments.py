"""Simultaneous call operands keep paths, rather than whole-owner reads."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute
from test_nested_record_field_moves import SOURCE

TAKE = '''take=(inner:Inner answer:int64):>int64=>{
 inner.values.push(42)
 return if answer=?42 and inner.values.length=?1025 inner.values[1024] else 1
}
'''
START, _ = SOURCE.split('work=')
WORK = '''work=():>int64=>{
 let box=make(1024)
 let before:int64=_arena_allocated_bytes
 let result=take(box.inner box.answer)
 if _arena_allocated_bytes-before>?1024 return 2
 return result
}
main=():>int64=>{let before:int64=_arena_live_bytes loop i in [0..20) {if work() not=?42 return 3} return if _arena_live_bytes=?before 42 else 4}
'''
CASES = [START+TAKE+WORK,
 (START+TAKE+WORK).replace('take(box.inner box.answer)', 'take(answer=box.answer inner=box.inner)'),
]
RESOURCE = '''let drops:int64=0
Handle=type of [value:int64
$__drop__
release=():>void=>{drops+=value}
]
Pair:type=[left:Handle right:Handle]
consume=(left:Handle right:Handle):>void=>{let a=left let b=right}
main=():>int64=>{let pair=Pair[Handle[20] Handle[22]] consume(pair.left pair.right) return drops}
'''
CASES.append(RESOURCE)
ERRORS = [(START+TAKE+WORK).replace('answer:int64):>int64', 'answer:Box):>int64').replace('answer=?42', 'answer.answer=?42').replace('take(box.inner box.answer)', 'take(box.inner box)'),
    (START+TAKE+WORK).replace('answer:int64):>int64', 'answer:Inner):>int64').replace('answer=?42', 'answer.values.length=?1024').replace('take(box.inner box.answer)', 'take(box.inner box.inner)'),
]

@pytest.mark.parametrize('source', CASES)
def test_disjoint_field_arguments(tmp_path, source):
    execute(tmp_path, 'disjoint-fields', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_overlapping_field_arguments_reject(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_disjoint_field_arguments(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
