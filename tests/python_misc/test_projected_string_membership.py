"""String membership narrows a stable projection without changing its store type."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HEADER = '''Box:type=[delims:string]
Result:type=[delims:('[]'|'[)')?]
put=(result:Result @state:int64):>Result=>result
'''
CASES = [HEADER + '''read=(node:Box @state:int64):>Result=>{
$runtime_assert node.delims is? '[]'|'[)'
return put(Result[node.delims] @state)
}
main=():>int64=>{let state:int64=0 let result=read(Box['[)'] @state) return if result.delims=?'[)' 42 else 1}''',
HEADER + '''read=(node:Box):>Result=>{
if node.delims isnt? '[]'|'[)' return Result[none]
return Result[node.delims]
}
main=():>int64=>if read(Box['[]']).delims=?'[]' and read(Box['xx']).delims=?none 42 else 1''',
'''read=(xs:array<string length=1>):>('[]'|'[)')?=>{
if xs[0] isnt? '[]'|'[)' return none
return xs[0]
}
main=():>int64=>if read(['[)'])=?'[)' and read(['xx'])=?none 42 else 1''',
'''read=(xs:dict<string string>):>('[]'|'[)')?=>{
if 'key' not in? xs return none
if xs['key'] isnt? '[]'|'[)' return none
return xs['key']
}
main=():>int64=>if read(['key' -> '[)'])=?'[)' and read(['key' -> 'xx'])=?none 42 else 1''',
HEADER + '''read=(@node:Box):>string=>{
if node.delims is? '[]'|'[)' {node.delims='replacement'}
return node.delims
}
main=():>int64=>{let node=Box['[]'] return if read(@node)=?'replacement' 42 else 1}''']
ERRORS = [HEADER + '''read=(@node:Box):>('[]'|'[)')?=>{
$runtime_assert node.delims is? '[]'|'[)'
node.delims='xx'
return node.delims
}''', HEADER + '''change=(@node:Box):>void=>{node.delims='xx'}
read=(@node:Box):>('[]'|'[)')?=>{
$runtime_assert node.delims is? '[]'|'[)'
change(@node)
return node.delims
}''']


@pytest.mark.parametrize('source', CASES)
def test_projected_string_membership(tmp_path, source):
    execute(tmp_path, 'string-membership', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_projected_string_membership_expires(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_projected_string_membership(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
