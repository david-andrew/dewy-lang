"""Return a stable field view by transferring from its dying owner."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
Box:type=[items:array<int64> spare:array<int64>]
make=(n:int64):>Box=>Box[[n 22] [3 4]]
take=(n:int64):>array<int64>=>{
    let owner=make(n)
    let result=owner.items
    if owner.spare.length not=?2 return []
    return result
}
work=():>int64=>{
    let items=take(20)
    if items.length not=?2 return 1
    items[0]=items[0]+1
    return items[0]+items[1]-1
}
main=():>int64=>{
    if work() not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in [0..1000) {if work() not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}
'''
CASES = [SOURCE,
    SOURCE.replace('let result=owner.items', 'const result=@owner.items'),
    SOURCE.replace('return result', 'loop true {return result}'),
    SOURCE.replace('let result=owner.items', 'let kept=owner.copy()\n    let result=owner.items')
          .replace('return result', 'if kept.items.length not=?2 return []\n    return result'),
    SOURCE.replace('Box:type=', 'Inner:type=').replace('make=(n:', 'Box:type=[nested:Inner]\nmake=(n:')
          .replace('=>Box[[n 22] [3 4]]', '=>Box[Inner[[n 22] [3 4]]]')
          .replace('owner.items', 'owner.nested.items').replace('owner.spare', 'owner.nested.spare'),
]
CASES.append(SOURCE.replace('take=(n:int64)', 'take=(n:int64 @kept:Box)')
    .replace('let items=take(20)', 'let kept=Box[[] []]\n    let items=take(20 @kept)')
    .replace('let result=owner.items', 'kept=owner.copy()\n    let result=owner.items')
    .replace('return items[0]+items[1]-1', 'if kept.items.length not=?2 or kept.items[0] not=?20 return 4\n    return items[0]+items[1]-1'))
RECORD = '''$explicit_copies
Part:type=[items:array<int64>]
Box:type=[part:Part spare:array<int64>]
make=():>Box=>Box[Part[[20 22]] [7]]
take=():>Part=>{let owner=make() let result=owner.part return result}
work=():>int64=>{let value=take() return if value.items.length=?2 value.items[0]+value.items[1] else 1}
main=():>int64=>{
    if work() not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in [0..1000) {if work() not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}
'''
CASES.append(RECORD)
# A caller keeps this storage. Ending the callee does not end that owner.
ERRORS = ['''$explicit_copies
Box:type=[items:array<int64>]
take=(owner:Box):>array<int64>=>{let result=owner.items return result}
main=():>int64=>{let box=Box[[20 22]] let values=take(box) return 42}
''',
    SOURCE.replace('let owner=make(n)', 'const owner=make(n)')
          .replace('let result=owner.items', 'let address=owner transmute int64\n    let result=owner.items'),
]

@pytest.mark.parametrize('source', CASES)
def test_returned_field_view(tmp_path, source):
    execute(tmp_path, 'returned-field-view', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_returned_view_needs_owned_unexposed_root(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_returned_field_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
