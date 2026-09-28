"""Numeric indexed facts describe the current selector, never its old value."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

LOOKUP = '''read=(rows:array<array<int64>> row:int64 column:int64):>int64=>{
    if row>=?0 and row<?rows.length and column>=?0 and column<?rows[row].length {
        return rows[row][column]
    }
    return 0
}
main=():>int64=>read([[42] []] 0 0)
'''
CASES = [(Path(__file__).parents[1] / 'fixtures/mutable_selector_facts.dewy').read_text(), LOOKUP,
    LOOKUP.replace('    if row>=?', '    const selected=row\n    if selected>=?').replace('row<?rows.length', 'selected<?rows.length').replace('rows[row]', 'rows[selected]').replace('        return rows[selected][column]', '        row=1\n        return rows[selected][column]'),
    LOOKUP.replace('    if row>=?', '    let selected=row\n    if selected>=?').replace('row<?rows.length', 'selected<?rows.length').replace('rows[row]', 'rows[selected]'),
]
ERRORS = [LOOKUP.replace('        return rows[row][column]', mutation + '''
        if row>=?0 and row<?rows.length {return rows[row][column]}
        return 0''') for mutation in ('row=1', 'row+=1', 'row=if column=?0 1 else 0', 'rows[row]=[]')]
ERRORS.append(LOOKUP.replace('        return rows[row][column]', '''let cursor=@row
        cursor=1
        if row>=?0 and row<?rows.length {return rows[row][column]}
        return 0'''))
ERRORS.append('change=(@value:int64):>void=>{value=1}\n' + LOOKUP.replace('        return rows[row][column]', '''change(@row)
        if row>=?0 and row<?rows.length {return rows[row][column]}
        return 0'''))
ERRORS.append('''read=(rows:array<array<int64>>):>int64=>{
loop row in [0..rows.length) {
    if row=?0 and rows[row].length>?0 {continue}
    return rows[row][0]
}
return 0
}''')

ERRORS.append(LOOKUP.replace('        return rows[row][column]', """let copied=rows
        row=1
        if row>=?0 and row<?copied.length {return copied[row][column]}
        return 0"""))
CASES.append("""sum=(rows:array<array<int64>>):>int64=>{
let result:int64=0
loop row in [0..rows.length) {
    loop column in [0..rows[row].length) {result+=rows[row][column]}
}
return result
}
main=():>int64=>sum([[20] [22]])""")

# The same route identity carries element values, not just nested lengths.
CASES.append('''read=(@xs:array<int64> slot:int64):>int64=>{
if slot<?0 or slot>=?xs.length return 0
if xs[slot]=?0 return 0
return 84//xs[slot]
}
main=():>int64=>{let xs:array<int64>=[2] return read(@xs 0)}''')
CASES.append('''read=(@xs:array<int64> slot:int64):>int64=>{
if slot<?0 or slot>=?xs.length return 0
xs[slot]=42
$assert xs[slot]=?42
return xs[slot]
}
main=():>int64=>{let xs:array<int64>=[0] return read(@xs 0)}''')

ERRORS.append(LOOKUP.replace('column:int64)', 'column:int64 next:int64)').replace('[[42] []] 0 0)', '[[42] []] 0 0 1)').replace('        return rows[row][column]', """let copied=rows
        row=next
        if row>=?0 and row<?copied.length {return copied[row][column]}
        return 0"""))

ERRORS.append('''read=(i:int64 next:int64):>int64=>{
let rows:array<array<int64>>=[[] []]
if i<?0 or i>=?rows.length return 0
rows[i].push(42)
let copied=rows
i=next
if i>=?0 and i<?copied.length {return copied[i][0]}
return 0
}''')


@pytest.mark.parametrize('source', CASES)
def test_mutable_selector_bounds(tmp_path, source):
    execute(tmp_path, 'selector-bounds', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_changed_selector_forgets_bounds(source):
    with pytest.raises(ReportException, match='bound|index|cannot prove'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_mutable_selector_bounds(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
