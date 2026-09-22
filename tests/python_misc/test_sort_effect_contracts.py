"""Sort key invocation contributes effects independently of handle evaluation."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''work=():>int64 & allocates=>{let items:array<int64>=[42 1]
items.sort() return items[1]}
main=():>int64=>work()''',
    '''key=(value:int64):>int64=>-value
work=():>int64 & allocates=>{let items:array<int64>=[1 42]
items.sort(key=@key) return items[0]}
main=():>int64=>work()''',
    '''work=():>int64 & allocates=>{let items:array<int64>=[1 42]
items.sort(key=(value:int64):>int64 & no_effects=>-value) return items[0]}
main=():>int64=>work()''',
    '''reorder=(@items:array<int64> key:(value:int64):>int64 & no_effects):>void & reads<items> & mutates<items> & allocates=>items.sort(key=@key)
main=():>int64=>{let items:array<int64>=[1 42]
reorder(@items (value:int64):>int64 & no_effects=>-value)
if items.length >? 0 return items[0]
return 0}''',
    '''ascending=(value:int64):>int64=>value
descending=(value:int64):>int64=>-value
work=(reverse:bool):>int64 & allocates=>{let items:array<int64>=[1 42]
let key=if reverse @descending else @ascending
items.sort(key=@key) return if reverse items[0] else items[1]}
main=():>int64=>work(true)''',
    '''ascending=(value:int64):>int64=>value
descending=(value:int64):>int64=>-value
work=():>int64 & allocates=>{let items:array<int64>=[1 42]
let key=@ascending key=@descending
items.sort(key=@key) return items[0]}
main=():>int64=>work()''',
    '''let reorder=<E:Effect>(@items:array<int64> key:(value:int64):>int64 & E):>void & reads<items> & mutates<items> & allocates & E=>items.sort(key=@key)
main=():>int64=>{let items:array<int64>=[1 42]
reorder(@items (value:int64):>int64 & no_effects=>-value)
if items.length >? 0 return items[0]
return 0}''',
    '''join=(parts:array<string>):>string & allocates=>parts.join('-')
main=():>int64=>if join(['a' 'b'])=?'a-b' 42 else 0''',
    '''let events:int64=0
let calls:int64=0
Key:type=(value:int64):>int64
key=(value:int64):>int64=>{calls+=1 return value}
choose=():>Key=>{events=events*10+1 return @key}
direction=():>bool=>{events=events*10+2 return false}
main=():>int64=>{
let empty:array<int64>=[]
empty.sort(reverse=direction() key=choose())
if events not=? 21 or calls not=? 0 return 1
events=0
let items:array<int64>=[42 1]
items.sort(key=choose() reverse=direction())
if events not=? 12 or calls not=? 2 return 2
return items[1]}
''',

    '''let text:string='before'
key=(value:int64):>int64=>{text='after' return value}
change=():>string=>{let items:array<int64>=[2 1] items.sort(key=@key) return 'before'}
wrapped=():>string=>change()
main=():>int64=>{let equal=text=?wrapped() return if equal and text=?'after' 42 else 1}''',

]
ERRORS = [
    '''let writes:int64=0
key=(value:int64):>int64=>{writes+=1 return value}
bad=(@items:array<int64>):>void & reads<items> & mutates<items> & allocates=>items.sort(key=@key)''',
    '''bad=(@items:array<int64> key:(value:int64):>int64):>void & reads<items> & mutates<items> & allocates=>items.sort(key=@key)''',
    '''let writes:int64=0
safe=(value:int64):>int64=>value
unsafe=(value:int64):>int64=>{writes+=1 return value}
bad=(@items:array<int64>):>void & reads<items> & mutates<items> & allocates=>{
let key=@safe key=@unsafe items.sort(key=@key)}''',
    '''let writes:int64=0
safe=(value:int64):>int64=>value
unsafe=(value:int64):>int64=>{writes+=1 return value}
bad=(@items:array<int64> flag:bool):>void & reads<items> & mutates<items> & allocates=>{
let key=if flag @safe else @unsafe items.sort(key=@key)}''',
    '''let writes:int64=0
key=(value:int64):>int64=>value
select=():>((value:int64):>int64 & no_effects)=>{writes+=1 return @key}
bad=(@items:array<int64>):>void & reads<items> & mutates<items> & allocates=>items.sort(key=select())''',
    '''bad=(@items:array<int64>):>void & reads<items> & mutates<items> & no allocates=>items.sort()''',
]

@pytest.mark.parametrize('source', CASES)
def test_sort_effect_contracts(tmp_path, source):
    execute(tmp_path, 'sort-effect-contract', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_sort_effect_contracts_rejected(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_sort_effect_contracts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
