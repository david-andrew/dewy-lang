"""An exiting owning wrapper may transfer a field and release its siblings."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

PRELUDE = '''let trace:int64=0
Token=type of [id:int64
$__drop__
release=():>void=>{trace=trace*10+id}
]
Pair:type=[first:Token second:Token]
'''
CASES = [
    PRELUDE + '''take=():>Token=>{let pair=Pair[Token[1] Token[2]] return pair.first}
work=():>int64=>{let token=take() return if trace=?2 and token.id=?1 42 else 1}
main=():>int64=>{let n=work() return if trace=?21 n else 2}''',
    PRELUDE + '''take=(pair:Pair):>Token=>pair.second
work=():>int64=>{let token=take(Pair[Token[1] Token[2]]) return if trace=?1 and token.id=?2 42 else 1}
main=():>int64=>{let n=work() return if trace=?12 n else 2}''',
    PRELUDE + '''Tree:type=[pair:Pair last:Token]
take=(tree:Tree):>Token=>tree.pair.first
work=():>int64=>{let token=take(Tree[Pair[Token[1] Token[2]] Token[3]])
return if trace=?32 and token.id=?1 42 else 1}
main=():>int64=>{let n=work() return if trace=?321 n else 2}''',
    PRELUDE + '''take=(which:bool):>Token=>{let pair=Pair[Token[1] Token[2]]
if which return pair.first
return pair.second}
work=(which:bool):>int64=>{let token=take(which) return if trace=?2 and token.id=?1 or trace=?1 and token.id=?2 42 else 1}
main=():>int64=>{if work(true) not=?42 or trace not=?21 return 1
trace=0 if work(false) not=?42 or trace not=?12 return 2 return 42}''',
    PRELUDE + '''Container:type=[items:array<Token> other:Token]
take=():>array<Token>=>{let box=Container[[Token[1] Token[2]] Token[3]] return box.items}
work=():>int64=>{let items=take() return if trace=?3 and items.length=?2 42 else 1}
main=():>int64=>{let before=_arena_live_bytes let count:int64=0
loop count<?100 {trace=0 if work() not=?42 or trace not=?321 return 1 count+=1}
return if _arena_live_bytes=?before 42 else 2}''',
    PRELUDE + '''Moved=type of [token:Token
$__drop__ release=():>void=>{trace=trace*10+9}
$__move__ relocate=():>Moved=>Moved[Token[4]]]
Box:type=[value:Moved other:Token]
take=():>Moved=>{let box=Box[Moved[Token[1]] Token[2]] return box.value}
work=():>int64=>{let item=take() return if trace=?21 and item.token.id=?4 42 else 1}
main=():>int64=>{let n=work() return if trace=?2194 n else 2}''',
]
CASES += [
    PRELUDE + '''Maybe:type=[token:Token? other:Token]
take=():>Token?=>{let box=Maybe[Token[1] Token[2]] return box.token}
work=():>int64=>{let token=take() return if trace=?2 and token isnt? none and token.id=?1 42 else 1}
main=():>int64=>{let n=work() return if trace=?21 n else 2}''',
    PRELUDE + '''take=():>Token<id=?1>=>{let pair=Pair[Token[1] Token[2]] return pair.first}
work=():>int64=>{let token=take() return if trace=?2 and token.id=?1 42 else 1}
main=():>int64=>{let n=work() return if trace=?21 n else 2}''',
]
ERRORS = [
    PRELUDE + 'take=(@pair:Pair):>Token=>pair.first',
    PRELUDE + '''Box=type of [token:Token $__drop__ release=():>void=>{trace=token.id}]
take=(box:Box):>Token=>box.token''',
    PRELUDE + '''take=(pair:Pair):>Token=>{const alias=@pair return alias.first}''',
    PRELUDE + '''take=(pair:Pair):>Pair=>{const alias=@pair return alias}''',
    '''Moved=type of [id:int64 $__drop__ release=():>void=>{}
$__move__ relocate=():>Moved=>Moved[2]]
Box:type=[item:Moved]
take=():>Moved<id=?1>=>{let box=Box[Moved[1]] return box.item}''',
]

@pytest.mark.parametrize('source', CASES)
def test_owning_field_return(source, tmp_path):
    execute(tmp_path, 'field-return', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_field_return_cannot_consume_borrowed_or_custom_owner(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_owning_field_returns(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
