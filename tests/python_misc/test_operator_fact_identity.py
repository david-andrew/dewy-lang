"""User operator names carry only their checked contracts, never builtin laws."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from dewy.semantic.check import typecheck_and_resolve
from test_scalar_projection import execute

ARITHMETIC = '''let __add__=(x:uint8 y:uint8):>uint8=>255
main=():>int64=>{
    DECL value=__add__(1 2)
    $assert value=?3
    return 42
}'''
COMPARISON = '''let __lt__=(x:uint8 y:uint8):>bool=>true
probe=(x:uint8 y:uint8):>int64=>{
    if __lt__(x y) {$assert y>?x}
    return 42
}
main=():>int64=>probe(2 1)'''
NEGATION = '''let __not__=(x:bool):>bool=>true
probe=(x:bool):>int64=>{
    if __not__(x) {$assert x=?false}
    return 42
}
main=():>int64=>probe(true)'''
ERRORS = [ARITHMETIC.replace('DECL', decl) for decl in ('let', 'const')]
ERRORS += [COMPARISON, NEGATION]
CASES = [source.replace('$assert', '$runtime_assert').replace('value=?3', 'value=?255').replace('y>?x', 'x>?y').replace('x=?false', 'x') for source in ERRORS]
# Written return facts still apply, even for a function with an operator name.
CASES.append(CASES[0].replace('__add__(1 2)', '1+2'))
CASES.append('''let __lt__=(x:uint8 y:uint8):>true & <x<?y> | false=>y>?x
probe=(x:uint8 y:uint8):>int64=>{
    if __lt__(x y) {$assert y>?x}
    return 42
}
main=():>int64=>probe(1 2)''')

CASES.append("""let __and__=(x:bool y:bool):>bool=>false
bump=(@count:int64):>bool=>{count+=1 return true}
main=():>int64=>{
    let count:int64=0
    if true and true return 1
    if false and bump(@count) return 2
    if count not=?1 return 3
    return 42
}""")

# Lowered BigInt helpers carry an explicit integer_operation tag even though
# their function binding is ordinary. Keep that checked identity available.
CASES.append("""narrow=(value:bigint):>int64=>{
    if value <? 0 or value >? 42 return 1
    return value as int64
}
main=():>int64=>narrow(42)""")

CASES.append((Path(__file__).resolve().parents[2]/'dewy/tests/length_terms.dewy').read_text())

@pytest.mark.parametrize('source', ERRORS)
def test_user_operator_cannot_supply_builtin_evidence(source):
    with pytest.raises(ReportException, match='assertion'):
        typecheck_and_resolve(SrcFile(None, source))

@pytest.mark.parametrize('source', CASES)
def test_user_operator_keeps_its_own_semantics(tmp_path, source):
    execute(tmp_path, 'operator-identity', codegen(SrcFile(None, source), debug_locations=False))

def test_native_operator_fact_identity(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
