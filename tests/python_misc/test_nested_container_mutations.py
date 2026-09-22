"""Container methods use live entry places, including enclosing snapshots."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''main=():>int64=>{let d:dict<int64 set<int64>>=[1->set[1]]
d[1].push(42) return if 42 in? d[1] 42 else 0}''',
    '''main=():>int64=>{let d:dict<int64 set<int64>>=[1->set[1]]
let saved=d d[1].push(42) return if 42 in? d[1] and 42 not in? saved[1] 42 else 0}''',
    '''main=():>int64=>{let d:dict<int64 dict<int64 int64>>=[1->[2->42]]
let saved=d d[1].clear return if d[1].length=?0 and saved[1].length=?1 and 2 in? saved[1] saved[1][2] else 0}''',
    '''main=():>int64=>{let d:dict<int64 set<int64>>=[1->set[42]]
if 42 in? d[1] return d[1].pop(42) return 0}''',
    '''main=():>int64=>{let d:dict<int64 set<int64>>=[1->set[42]]
let saved=d d[1].clear return if d[1].length=?0 and 42 in? saved[1] 42 else 0}''',
]
CASES += [
    """let calls:int64=0
let drops:int64=0
Handle=type of [id:int64 $__drop__ release=():>void=>{drops+=1}]
key=():>'a'=>{calls+=1 return 'a'}
main=():>int64=>{let d:dict<'a' dict<int64 Handle>>=['a'->[1->Handle[1] 2->Handle[2]]]
d[key()].clear return if calls=?1 and drops=?2 42 else 0}""",

    """let calls:int64=0
key=():>'a'=>{calls+=1 return 'a'}
main=():>int64=>{let d:totaldict<'a' set<int64>>=['a'->set[1]]
d[key()].push(42) return if calls=?1 and 42 in? d['a'] 42 else 0}""",
    """main=():>int64=>{let d:dict<int64 set<int64>>=[1->set[1] 2->set[2]]
d.pop(1); let saved=d d[2].push(42)
return if 42 in? d[2] and 42 not in? saved[2] 42 else 0}""",
    """main=():>int64=>{let d:dict<int64 dict<int64 set<int64>>>=[1->[2->set[0]]]
let saved=d if 2 in? d[1] and 2 in? saved[1] {
d[1][2].push(42) return if 42 in? d[1][2] and 42 not in? saved[1][2] 42 else 0}
return 0}""",
]
ERRORS = [
    """change=(@d:dict<int64 set<int64>>):>int64=>{d.clear return 42}
main=():>int64=>{let d:dict<int64 set<int64>>=[1->set[1]]
d[1].push(change(@d)) return 42}""",
    """main=():>int64=>{let d:dict<int64 set<int64>>=[1->set[42]]
if 42 in? d[1] {d[1].clear return d[1].pop(42)} return 42}""",
    """main=():>int64=>{let d:dict<int64 set<int64>>=[1->set[1]]
const entry=@d[1] d[1].push(42) return if 42 in? entry 42 else 0}""",

    '''main=():>int64=>{const d:dict<int64 set<int64>>=[1->set[1]]
d[1].push(42) return 42}''',
    '''Box:type=const [d:dict<int64 set<int64>>]
main=():>int64=>{let box=Box[[1->set[1]]] box.d[1].push(42) return 42}''',
    '''main=():>int64=>{let d:dict<int64 set<int64>>=[]
d[1].push(42) return 42}''',
    '''f=(@d:dict<int64 set<int64>>):>void & no_effects=>{
if 1 in? d {d[1].push(42)}}''',
]

@pytest.mark.parametrize('source', CASES)
def test_nested_container_mutations(tmp_path, source):
    execute(tmp_path, 'nested-container', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_nested_container_restrictions(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_nested_container_mutations(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
