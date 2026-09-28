"""Uniform element exclusions survive storage and invalidate on foreign writes."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic.check import typecheck_and_resolve
from test_scalar_projection import execute

SCALAR = '''probe=(a:int64 b:int64):>int64=>{
    if a=?b return 0
    let values:array<int64>=[]
    values.push(a)
    if values.length=?0 return 0
    let saved=values[0]
    $assert saved not=?b
    return 42
}
main=():>int64=>probe(8 4)'''
RECORD = SCALAR.replace('probe=', 'Item:type=[value:int64]\nprobe=', 1).replace('array<int64>', 'array<Item>').replace('values.push(a)', 'values.push(Item[a])').replace('$assert saved not=?b', '$assert saved.value not=?b')
CASES = [SCALAR, RECORD,
    SCALAR.replace('values.push(a)', 'values.push(a)\n    a=b'),
    SCALAR.replace('values.push(a)', 'values.push(a)\n    values.push(a)'),
    SCALAR.replace('    if values.length=?0 return 0\n    let saved=values[0]\n    $assert saved not=?b', '    loop saved in values {$assert saved not=?b}'),
    SCALAR.replace('if a=?b', 'if a=?0').replace('$assert saved not=?b', '$assert saved not=?0'),
]
ERRORS = [SCALAR.replace('values.push(a)', 'values.push(a)\n    values.clear\n    values.push(b)'),
    SCALAR.replace('values.push(a)', 'values.push(a)\n    values.push(b)'),
    SCALAR.replace('    let saved=values[0]', '    values[0]=b\n    let saved=values[0]'),
    SCALAR.replace('    $assert saved not=?b', '    b=saved\n    $assert saved not=?b'),
    RECORD.replace('    let saved=values[0]', '    values[0].value=b\n    let saved=values[0]'),
    CASES[-1].replace('values.push(a)', 'values.push(a)\n    values.push(0)'),
]

# A comparison refers to the value observed before its later operand runs.
CASES.append("""reset=(@value:int64):>int64=>{value=0 return 0}
probe=(value:int64):>int64=>{
    if value=?0 return 0
    if value not=? reset(@value) return 42
    return 0
}
main=():>int64=>probe(8)""")
ERRORS.append("""change=(@value:int64):>int64=>{value=1 return 0}
main=():>int64=>{
    let value:int64=0
    $assert value not=?change(@value)
    return 42
}""")


CASES.append(CASES[5].replace('$assert saved not=?0', '$assert 0 not=?saved').replace('    return 42', '    return 336//saved'))
ERRORS.extend([
    """Box:type=[value:int64]
probe=(box:Box):>int64=>{
    if box.value=?0 return 0
    box.value=0
    return 42//box.value
}
main=():>int64=>probe(Box[8])""",
    """probe=(values:array<int64>):>int64=>{
    if values.length=?0 return 0
    values.clear
    return 42//values.length
}
main=():>int64=>probe([8])""",
    SCALAR.replace('if a=?b', 'if a>=?b').replace('values.push(a)', 'values.push(a)\n    values.clear\n    values.push(b)').replace('$assert saved not=?b', '$assert saved <? b'),
    SCALAR.replace('values.push(a)', 'values.push(a)\n    values.clear\n    values.push(b)').replace('$assert saved not=?b', '$assert saved not=?saved'),
])


CASES.append(SCALAR.replace('    if values.length=?0 return 0', '    let copied=values.copy()\n    values.clear\n    if copied.length=?0 return 0').replace('let saved=values[0]', 'let saved=copied[0]'))


@pytest.mark.parametrize('source', CASES)
def test_element_exclusions(tmp_path, source):
    execute(tmp_path, 'element-exclusions', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_element_exclusions_need_every_element_and_current_terms(source):
    with pytest.raises(ReportException):
        typecheck_and_resolve(SrcFile(None, source))


def test_native_element_exclusions(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
