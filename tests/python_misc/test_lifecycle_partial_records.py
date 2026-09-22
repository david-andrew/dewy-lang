"""Disjoint record fields retain independent ownership after a component move."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute
from test_lifecycle_field_returns import PRELUDE

CASES=[
    PRELUDE+'''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let first=pair.first
return if first.id=?1 and pair.second.id=?2 and trace=?0 42 else 1}
main=():>int64=>{let result=work() return if trace=?12 result else 2}''',
    PRELUDE+'''work=():>int64=>{let pair=Pair[Token[1] Token[2]]
let first=pair.first let second=pair.second return if first.id+second.id=?3 42 else 1}
main=():>int64=>{let result=work() return if trace=?21 result else 2}''',
    PRELUDE+'''Tree:type=[pair:Pair last:Token]
work=():>int64=>{let tree=Tree[Pair[Token[1] Token[2]] Token[3]]
let first=tree.pair.first let second=tree.pair.second
return if first.id+second.id+tree.last.id=?6 42 else 1}
main=():>int64=>{let result=work() return if trace=?213 result else 2}''',
    PRELUDE+'''take=():>Token=>{let pair=Pair[Token[1] Token[2]] let first=pair.first return pair.second}
work=():>int64=>{let second=take() return if trace=?1 and second.id=?2 42 else 1}
main=():>int64=>{let result=work() return if trace=?12 result else 2}''',
    PRELUDE+'''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let first=pair.first
pair.second=Token[3] return if first.id=?1 and pair.second.id=?3 and trace=?2 42 else 1}
main=():>int64=>{let result=work() return if trace=?213 result else 2}''',
    PRELUDE+'''Box:type=[items:array<Token> other:Token]
work=():>int64=>{let box=Box[[Token[1] Token[2]] Token[3]] let items=box.items
return if items.length=?2 and box.other.id=?3 42 else 1}
main=():>int64=>{let before=_arena_live_bytes let count:int64=0
loop count<?100 {trace=0 if work() not=?42 or trace not=?213 return 1 count+=1}
return if _arena_live_bytes=?before 42 else 2}''',
    PRELUDE+'''Maybe:type=[first:Token? second:Token]
work=():>int64=>{let pair=Maybe[Token[1] Token[2]] let first=pair.first let second=pair.second
return if first isnt? none and first.id+second.id=?3 42 else 1}
main=():>int64=>{let result=work() return if trace=?21 result else 2}''',
]
CASES += [
    PRELUDE+'''take=(flag:bool):>Token?=>{let pair:Pair|none=if flag Pair[Token[1] Token[2]] else none
if pair isnt? none return pair.first return none}
work=():>int64=>{let token=take(true) return if trace=?2 and token isnt? none and token.id=?1 42 else 1}
main=():>int64=>{let result=work() return if trace=?21 result else 2}''',
    PRELUDE+'''Node:type=[item:Token children:array<Node>]
take=():>Token?=>{let root=Node[Token[1] [Node[Token[2] []]]]
if root.children.length>?0 return root.children[0].item return none}
work=():>int64=>{let token=take() return if trace=?1 and token isnt? none and token.id=?2 42 else 1}
main=():>int64=>{let before=_arena_live_bytes let result=work()
return if trace=?12 and _arena_live_bytes=?before result else 2}''',
]
CASES += [PRELUDE+'''Moved=type of [token:Token
$__drop__ release=():>void=>{trace=trace*10+9}
$__move__ relocate=():>Moved=>Moved[Token[4]]]
Box:type=[value:Moved other:Token]
work=():>int64=>{let box=Box[Moved[Token[1]] Token[2]]
let item=box.value let other=box.other
return if trace=?0 and item.token.id=?4 and other.id=?2 42 else 1}
main=():>int64=>{let result=work() return if trace=?2941 result else 2}''']
ERRORS=[
    PRELUDE+'work=(pair:Pair):>int64=>{let first=pair.first return pair.first.id+first.id}',
    PRELUDE+'work=(pair:Pair):>Pair=>{let first=pair.first return pair}',
    PRELUDE+'''Tree:type=[pair:Pair last:Token]
work=(tree:Tree):>Pair=>{let first=tree.pair.first return tree.pair}''',
    PRELUDE+'''consume=(pair:Pair):>int64=>pair.second.id
work=(pair:Pair):>int64=>{let first=pair.first return consume(pair)}''',
    PRELUDE+'work=(pair:Pair):>int64=>{const alias=@pair let first=pair.first return alias.second.id+first.id}',
    PRELUDE+'work=(@pair:Pair):>int64=>{let first=pair.first return first.id+pair.second.id}',
    PRELUDE+'''Hooked=type of [first:Token second:Token $__drop__ release=():>void=>{trace=first.id}]
work=(pair:Hooked):>int64=>{let first=pair.first return first.id+pair.second.id}''',
]

@pytest.mark.parametrize('source',CASES)
def test_disjoint_components_keep_their_owners(source,tmp_path):
    execute(tmp_path,'partial-record',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_partial_owner_cannot_be_used_as_a_complete_value(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source))

def test_native_partial_records(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
