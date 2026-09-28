"""Guard evidence must describe machine arithmetic, including possible wrap."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from dewy.semantic.check import typecheck_and_resolve
from test_scalar_projection import execute

BASE = '''probe=(x:WORD limit:WORD):>int64=>{
    if x+1<?limit {$assert x<?limit}
    return 42
}
main=():>int64=>probe(8 10)'''
ERRORS = [BASE.replace('WORD', word) for word in ('uint8', 'int8', 'uint64', 'int64')]
ERRORS += [s.replace('x+1<?limit', 'x-1>?limit').replace('$assert x<?limit', '$assert x>?limit') for s in ERRORS.copy()]
ERRORS.append('let __add__=(x:uint8 step:uint8):>uint8=>0\n'+BASE.replace('WORD', 'uint8').replace('x+1<?limit', '__add__(x 1)<?limit'))
CASES = [BASE.replace('WORD', word).replace('    if x+1', '    if x>=?20 return 42\n    if x+1') for word in ('uint8', 'int8', 'uint64', 'int64')]
CASES += [BASE.replace('WORD', word).replace('    if x+1<?limit', '    if x<=?0 return 42\n    if x-1>?limit').replace('$assert x<?limit', '$assert x>?limit').replace('probe(8 10)', 'probe(10 8)') for word in ('uint8', 'int8', 'uint64', 'int64')]

STORED = """probe=(x:uint8 bound:uint8):>int64=>{
    if x>?bound return 0
    let saved=x-1
    $assert saved<=?bound
    return 42
}
main=():>int64=>probe(8 10)"""
ERRORS.append(STORED)
CASES.append(STORED.replace('    if x>?bound', '    if x=?0 return 0\n    if x>?bound'))
ERRORS.append('let __sub__=(x:uint8 step:uint8):>uint8=>255\n'+STORED.replace('let saved=x-1', 'let saved=__sub__(x 1)'))

@pytest.mark.parametrize('source', ERRORS)
def test_wrapping_guard_cannot_supply_integer_order(source):
    with pytest.raises(ReportException, match='assertion'):
        typecheck_and_resolve(SrcFile(None, source))

@pytest.mark.parametrize('source', CASES)
def test_nonwrapping_guard_supplies_integer_order(tmp_path, source):
    execute(tmp_path, 'nonwrapping-guard', codegen(SrcFile(None, source), debug_locations=False))

def test_native_affine_guard_wrap(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
