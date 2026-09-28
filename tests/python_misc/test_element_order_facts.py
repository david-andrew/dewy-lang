"""Array element evidence preserves both sides of an ordering relation."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic.check import typecheck_and_resolve
from test_scalar_projection import execute

SCALAR = '''probe=(a:int64 b:int64):>int64=>{
    if a<=?b return 0
    let values:array<int64>=[]
    values.push(a)
    if values.length=?0 return 0
    let saved=values[0]
    $assert saved >?b
    return 42
}
main=():>int64=>probe(8 4)'''
RECORD = SCALAR.replace('probe=', 'Item:type=[value:int64]\nprobe=', 1).replace('array<int64>', 'array<Item>').replace('values.push(a)', 'values.push(Item[a])').replace('$assert saved >?b', '$assert saved.value >?b')
CASES = [SCALAR, RECORD,
    SCALAR.replace('values.push(a)', 'values.push(a)\n    a=b'),
    SCALAR.replace('values.push(a)', 'values.push(a)\n    values.push(a)'),
    SCALAR.replace('    if values.length=?0 return 0\n    let saved=values[0]\n    $assert saved >?b', '    loop saved in values {$assert saved >?b}'),
    SCALAR.replace('    if values.length=?0 return 0', '    let copied=values.copy()\n    values.clear\n    if copied.length=?0 return 0').replace('let saved=values[0]', 'let saved=copied[0]'),
]
ERRORS = [SCALAR.replace('values.push(a)', 'values.push(a)\n    values.clear\n    values.push(b)'),
    SCALAR.replace('values.push(a)', 'values.push(a)\n    values.push(b)'),
    SCALAR.replace('    let saved=values[0]', '    values[0]=b\n    let saved=values[0]'),
    SCALAR.replace('    $assert saved >?b', '    b=saved\n    $assert saved >?b'),
    RECORD.replace('    let saved=values[0]', '    values[0].value=b\n    let saved=values[0]'),
]

# Numeric intervals use the same uniform-element meet as relational facts.
INTERVAL = SCALAR.replace('if a<=?b', 'if a<?1 or a>?10').replace('$assert saved >?b', '$assert saved >=?1 and saved <=?10')
CASES.extend([INTERVAL, INTERVAL.replace('values.push(a)', 'values.push(a)\n    a=0'),
              INTERVAL.replace('let saved=values[0]\n    $assert saved >=?1 and saved <=?10', '$assert values[0] >=?1 and values[0] <=?10'),
              INTERVAL.replace('probe=', 'Item:type=[value:int64]\nprobe=', 1).replace('array<int64>', 'array<Item>').replace('values.push(a)', 'values.push(Item[a])').replace('saved >=?1 and saved <=?10', 'saved.value >=?1 and saved.value <=?10')])
ERRORS.extend([INTERVAL.replace('values.push(a)', 'values.push(a)\n    values.push(b)'),
               INTERVAL.replace('values.push(a)', 'values.push(a)\n    values.clear\n    values.push(b)')])

CASES.append("""Item:type=[value:int64 spare:int64]
main=():>int64=>{
    let a:int64=0
    let item=Item[a {a=8 0}]
    $assert item.value=?0 and a=?8
    return 42
}""")
ERRORS.extend([
    """Item:type=[value:int64 spare:int64]
main=():>int64=>{
    let a:int64=0
    let item=Item[a {a=8 0}]
    $assert item.value>?0
    return 42
}""",
    """Item:type=[value:int64 spare:int64]
main=():>int64=>{
    let a:int64=0
    let values:array<Item>=[]
    values.push(Item[a {a=8 0}])
    $assert values.length>?0
    let saved=values[0]
    $assert saved.value>?0
    return 42
}""",
    """main=():>int64=>{
    let a:int64=0
    let values:array<int64>=[]
    values.insert(a {a=8 0})
    $assert values.length>?0
    let saved=values[0]
    $assert saved>?0
    return 42
}""",
])

@pytest.mark.parametrize('source', CASES)
def test_element_order(tmp_path, source):
    execute(tmp_path, 'element-order', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_element_order_requires_current_uniform_evidence(source):
    with pytest.raises(ReportException):
        typecheck_and_resolve(SrcFile(None, source))

def test_native_element_order(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
