"""A stored sequence keeps facts about its length without aliasing the source."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from dewy.semantic.check import typecheck_and_resolve
from test_scalar_projection import execute

BASE = '''probe=(text:string bound:int64):>int64=>{
    if text.length<=?bound return 0
    let values:array<string>=[]
    values.push(text)
    if values.length=?0 return 0
    let saved=values[0]
    $assert saved.length>?bound
    return 42
}
main=():>int64=>probe("hello" 2)'''
CASES = [BASE,
    BASE.replace('values.push(text)', 'values.push(text)\n    text=""'),
    BASE.replace('values.push(text)', 'values.push(text)\n    values.push(text)'),
    BASE.replace('    if values.length=?0 return 0\n    let saved=values[0]\n    $assert saved.length>?bound',
                 '    loop saved in values {$assert saved.length>?bound}'),
    BASE.replace('    if values.length=?0 return 0', '    let copied=values.copy()\n    values.clear\n    if copied.length=?0 return 0').replace('let saved=values[0]', 'let saved=copied[0]'),
    BASE.replace('text.length<=?bound', 'text.length>=?bound').replace('saved.length>?bound', 'saved.length<?bound').replace('"hello" 2', '"hello" 8'),
    BASE.replace('text.length<=?bound', 'text.length=?bound').replace('saved.length>?bound', 'saved.length not=?bound'),
    BASE.replace('text.length<=?bound', 'text.length<?2 or text.length>?8').replace('saved.length>?bound', 'saved.length>=?2 and saved.length<=?8'),
    BASE.replace('text:string', 'text:array<int64>').replace('array<string>', 'array<array<int64>>').replace('"hello" 2', '[1 2 3] 2'),
]
CASES.extend([
    BASE.replace('if text.length<=?bound', 'if bound<?0 or bound>=?text.length').replace('$assert saved.length>?bound', 'let letter=saved[bound]\n    $assert letter.length=?1'),
])

OFFSET = 'size=(src:string):>int64<v=>0<=?v<=?src.length>=>src.length\nprobe=(text:string offset:int64):>int64=>{\n    if offset<?0 or offset>?text.length return 0\n    let count=size(text[offset..])\n    let values:array<int64>=[]\n    values.push(offset)\n    if values.length=?0 return 0\n    let saved=values[0]\n    let part=text[saved..saved+count)\n    return 42\n}\nmain=():>int64=>probe("hello" 1)'
SEQUENCE = OFFSET.replace('array<int64>', 'array<string>').replace('values.push(offset)', 'values.push(text)').replace('text[saved..saved+count)', 'saved[offset..offset+count)')
CASES.extend([OFFSET, SEQUENCE])

ERRORS = [BASE.replace('values.push(text)', 'values.push(text)\n    values.push("")'),
    BASE.replace('values.push(text)', 'values.push(text)\n    values.clear\n    values.push("")'),
    BASE.replace('    let saved=values[0]', '    values[0]=""\n    let saved=values[0]'),
    BASE.replace('    $assert saved.length>?bound', '    bound=saved.length\n    $assert saved.length>?bound'),
]

ARRAY = BASE.replace('text:string', 'text:array<int64>').replace('array<string>', 'array<array<int64>>').replace('"hello" 2', '[1 2 3] 2')
CASES.append(ARRAY.replace('values.push(text)', 'values.push(text)\n    text.clear'))
ERRORS.append(ARRAY.replace('    let saved=values[0]', '    values[0].clear\n    let saved=values[0]'))

ERRORS.extend([OFFSET.replace('    let part=', '    count=text.length\n    let part='),
               SEQUENCE.replace('    let part=', '    values[0]=""\n    let shortened=values[0]\n    let part=').replace('saved[offset..offset+count)', 'shortened[offset..offset+count)')])

@pytest.mark.parametrize('source', CASES)
def test_element_sequence_facts(tmp_path, source):
    execute(tmp_path, 'element-sequence', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_element_sequence_requires_current_uniform_evidence(source):
    with pytest.raises(ReportException):
        typecheck_and_resolve(SrcFile(None, source))

def test_native_element_sequence_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
