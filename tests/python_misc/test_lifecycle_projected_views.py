"""Required resource views share rooted storage without acquiring an owner."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

HEADER='''let drops:int64=0
Token=type of [id:int64 payload:array<int64>
$__drop__ release=():>void=>{drops+=1 payload.clear}]
'''
CASES=[
    HEADER+'''work=():>int64=>{let items=[Token[42 [7]]]
const item=@items[0]
if item.payload.length not=?1 or item.payload[0] not=?7 return 1
return item.id}
main=():>int64=>{let before:int64=_arena_live_bytes let answer=work()
return if drops=?1 and _arena_live_bytes=?before answer else 2}''',
    HEADER+'''Box:type=[value:Token other:int64]
work=():>int64=>{let box=Box[Token[42 [7]] 0]
const item=@box.value
return item.id}
main=():>int64=>{let answer=work() return if drops=?1 answer else 2}''',
    HEADER+'''work=():>int64=>{let items=[Token[1 [1]] Token[2 [2]]]
loop i in [0..items.length) {const item=@items[i]
if item.id not=?i+1 return 1
if item.payload.length not=?1 or item.payload[0] not=?i+1 return 2}
return 42}
main=():>int64=>{let before:int64=_arena_live_bytes
loop i in [0..20) {if work() not=?42 return 3}
return if drops=?40 and _arena_live_bytes=?before 42 else 4}''',
]
CASES.extend([
    HEADER+'''work=():>int64=>{let owners:dict<string Token>=['x'->Token[42 [7]]]
if 'x' not in? owners return 1
const item=@owners['x'] const alias=@item return alias.id}
main=():>int64=>{let answer=work() return if drops=?1 answer else 2}''',
    HEADER+'''work=():>int64=>{let items=[Token[42 [7]] Token[2 [8]]]
let index:int64=0 const item=@items[index] index=1 return item.id}
main=():>int64=>{let answer=work() return if drops=?2 answer else 1}''',
])

# Detaching an array can relocate even an untouched element. Until that
# storage lifetime is proven, sibling writes still conflict with the view.
ERRORS=[
    HEADER+'''work=():>int64=>{let items=[Token[42 [7]] Token[2 [8]]]
const item=@items[0] items[1].id=3 return item.id}
main=():>int64=>{let answer=work() return if drops=?2 answer else 1}''',

    HEADER+'''work=():>int64=>{let items=[Token[42 [7]]]
const item=@items[0] items.clear return item.id}''',
    HEADER+'''consume=(value:Token):>void=>{}
work=(flag:bool):>int64=>{let items=[Token[42 [7]]]
const item=@items[0] if flag {consume(items[0]);} return item.id}''',
    HEADER+'''consume=(value:Token):>void=>{}
work=():>int64=>{let items=[Token[42 [7]]]
const item=@items[0] consume(item) return items[0].id}''',
    HEADER+'''work=():>Token=>{let items=[Token[42 [7]]]
const item=@items[0] return item}''',
    HEADER+'''consume=(values:array<Token>):>void=>{}
work=():>int64=>{let items=[Token[42 [7]]]
const item=@items[0] consume(items) return item.id}''',
    HEADER+'''work=():>int64=>{let items=[Token[42 [7]]]
const item=@items[0] items[0]=Token[3 [8]] return item.id}''',
]

# Logical view conflicts must also reject in unused source functions, before
# native reachability can prune their bodies.
UNUSED_ERRORS=[source for source in ERRORS if '\nmain=' not in source]
for source in UNUSED_ERRORS:
    call = 'work(false)' if 'flag:bool' in source else 'work().id' if ':>Token=>' in source else '42+work()'
    ERRORS.append(source+f'\nmain=():>int64=>{call}')

@pytest.mark.parametrize('source', CASES)
def test_projected_resource_view(tmp_path,source):
    execute(tmp_path,'resource-view',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source', ERRORS)
def test_resource_view_cannot_lose_its_owner(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source))


def test_native_projected_resource_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
