"""Mutable local places retain their selected storage through the last use."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

CASES = [
    '''let put=<T>(@xs:array<T length=1> value:T):>void=>{let cursor=@xs[0] cursor=value}
main=():>int64=>{let xs:array<int64 length=1>=[0] put(@xs 42) return xs[0]}''',
    '''main=():>int64=>{let xs:array<int64>=[0 0]
loop i in [0..2) {let cursor=@xs[i] cursor=21}
return xs[0]+xs[1]}''',
    '''main=():>int64=>{let xs:array<int64>=[1]
if xs[0]=?1 {let cursor=@xs[0] cursor=42}
return xs[0]}''',
    '''let drops:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{drops+=1}
]
probe=():>int64=>{let xs:array<Handle>=[Handle[1]] let cursor=@xs[0]
cursor=Handle[42]
return xs[0].id}
main=():>int64=>{let answer=probe() return if drops=?2 answer else 0}''',
    '''$explicit_copies
put=(@xs:array<int64 length=1>):>void=>{let cursor=@xs[0] cursor=42}
main=():>int64=>{let xs:array<int64 length=1>=[1] put(@xs) return xs[0]}''',
    '''main=():>int64 & no_effects=>{let x:int64=0 let cursor=@x cursor=42 return x}''',

    '''main=():>int64=>{let x:int64=0 let cursor=@x cursor=42
let answer:int64<v=>v=?cursor>=x
return answer}''',
    '''Box:type=[items:array<int64>]
main=():>int64=>{let box=Box[[42]] let cursor=@box
let answer:int64<v=>v=?cursor.items.length>=box.items.length
return answer+41}''',
    '''main=():>int64=>{let xs:array<int64>=[0] let cursor=@xs[0] cursor=42
let answer:int64<v=>v=?cursor>=xs[0]
return answer}''',

    '''main=():>int64=>{let xs:array<int64>=[0] let cursor=@xs[0]
cursor=42
$assert cursor=?42
$assert xs[0]=?42
return cursor}''',
    '''main=():>int64=>{let xs:array<int64>=[0] let cursor=@xs[0]
let next=@cursor
next=42
return cursor}''',
    '''main=():>int64=>{let value:int64=1 let cursor=@value cursor=42 return value}''',
    '''Box:type=[value:int64]
main=():>int64=>{let box=Box[40] let cursor=@box.value cursor+=2 return box.value}''',
    '''main=():>int64=>{let xs:array<int64>=[40 0] let i:int64=0
let cursor=@xs[i]
i=1
cursor+=2
return xs[0]+xs[1]}''',
    '''let calls:int64=0
select=():>int64<v=>v=?0>=>{calls+=1 return 0}
main=():>int64=>{let xs:array<int64>=[40] let cursor=@xs[select()]
cursor+=1 cursor+=1
return if calls=?1 xs[0] else 0}''',
    '''main=():>int64=>{let xs:array<int64>=[40] let cursor=@xs[0]
let old=xs
cursor=42
return if old[0]=?40 xs[0] else 0}''',
    '''read=(@xs:array<int64 length=1>):>int64=>{
let cursor=@xs[0]
if cursor=?0 return 0
return 84//cursor
}
main=():>int64=>{let xs:array<int64 length=1>=[2] return read(@xs)}''',
    '''set=(@value:int64):>void=>{value=42}
main=():>int64=>{let xs:array<int64>=[0] let cursor=@xs[0] set(@cursor) return xs[0]}''',
    '''main=():>int64=>{let xs:array<int64>=[0] let cursor=@xs[0]
loop i in [0..42) {cursor+=1}
return xs[0]}''',
    # Replacing the owner after the place's last use is allowed.
    '''main=():>int64=>{let xs:array<int64>=[0] let cursor=@xs[0]
cursor=1
xs.clear xs.push(42)
return xs[0]}''',
]
ERRORS = [
    # Writes through a projected alias also invalidate the owner's narrowing.
    '''Box:type=[value:int64]
main=():>int64=>{let box=Box[1] let cursor=@box
if box.value not=?0 {cursor.value=0 return 84//box.value}
return 0}''',
    '''main=():>int64=>{let xs:array<int64>=[1] let cursor=@xs[0]
if xs[0] not=?0 {cursor=0 return 84//xs[0]}
return 0}''',
    '''bad=(@xs:array<int64 length=1>):>void & no_effects=>{let cursor=@xs[0] cursor=42}''',
    '''main=():>int64=>{let xs:array<int64<v=>v>=?0>>=[1]
let cursor=@xs[0] cursor=-1 return 42}''',
    '''main=():>int64=>{let x:int64=1 let cursor=@x
read=():>int64=>cursor
cursor=42 return read()}''',

    '''main=():>int64=>{let x:int64=0 let cursor=@x cursor=42
let answer:int64<v=>v=?cursor>=41
return answer}''',
    '''Box:type=[items:array<int64>]
main=():>int64=>{let box=Box[[42]] let cursor=@box
let answer:int64<v=>v=?cursor.items.length>=0
return answer}''',

    # A broader alias annotation cannot discard the owner's write contract.
    '''main=():>int64=>{let value:int64<v=>v>=?0>=1
let cursor:int64=@value
cursor=-1
return value}''',
    # A later owner's write must invalidate source-checker alias narrowing.
    '''main=():>int64=>{let xs:array<int64>=[1] let cursor=@xs[0]
if cursor not=?0 {xs[0]=0 return 84//cursor}
return 0}''',
    '''bad=(@xs:array<int64> i:int64):>int64=>{let unused=@xs[i] return 42}''',
    # Forming an unused place still owes the index proof at the declaration.
    '''main=():>int64=>{let xs:array<int64>=[] let cursor=@xs[0] return 42}''',
    '''main=():>int64=>{let xs:array<int64>=[1] let cursor=@xs[0]
let second=@cursor
xs.clear xs.push(2)
second=42
return xs[0]}''',
    '''main=():>int64=>{const value:int64=1 let cursor=@value cursor=42 return value}''',
    '''Box:type=[const value:int64]
main=():>int64=>{let box=Box[1] let cursor=@box.value cursor=42 return box.value}''',
    '''main=():>int64=>{let xs:array<int64>=[1] let cursor=@xs[0]
xs.clear xs.push(2)
cursor=42
return xs[0]}''',
    '''Box:type=[value:int64]
main=():>int64=>{let box=Box[1] let cursor=@box.value box=Box[2] cursor=42 return box.value}''',
    '''main=():>int64=>{let value:int64<v=>v>=?0>=1 let cursor=@value cursor=-1 return value}''',
]

@pytest.mark.parametrize('source', CASES)
def test_mutable_local_place(tmp_path, source):
    execute(tmp_path, 'local-place', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_mutable_local_place_rejected(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_mutable_local_places(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
