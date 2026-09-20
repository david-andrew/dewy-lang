from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic import ty
from dewy.semantic.effect_rows import Contract, Row
from tests.python_misc.test_scalar_projection import execute


@pytest.mark.parametrize('source', [
    'f=(x:int64):>int64 & no_effects=>x+1',
    'f=(xs:array<int64>):>int64 & Effect<>=>xs.length',
    'f=():>int64 & no_effects=>{let x:int64=0 x+=42 return x}',
    'g=(x:int64):>int64=>x+1\nf=(x:int64):>int64 & no_effects=>g(x)',
    'f=(x:int64):>int64 & no_effects=>if x>?0 g(x-1) else 42\ng=(x:int64):>int64=>f(x)',
    'f=(xs:array<int64 length=1>):>int64 & no_effects=>xs[0]',
    'f=(callback:():>int64 & no_effects):>int64 & no_effects=>callback()',
    'f=(x:int64=42):>int64 & no_effects=>x',
])
def test_pure_scalar_and_read_only_value_paths(source):
    codegen(SrcFile(None, source))


@pytest.mark.parametrize('source', [
    'f=():>void & no_effects=>printl("observable")',
    'f=(@x:int64):>void & no_effects=>{x=42}',
    'f=(@x:int64):>int64 & no_effects=>x',
    'let x:int64=42\nf=():>int64 & no_effects=>x',
    'f=(callback:():>int64):>int64 & no_effects=>callback()',
    'f=(xs:array<int64>):>array<int64> & no_effects=>xs.copy()',
    'f=(x:bool):>void & no_effects=>{$runtime_assert x}',
    'g=():>int64=>{printl("observable") return 42}\nf=():>int64 & no_effects=>g()',
    'g=():>int64=>{printl("default") return 42}\nf=(x:int64=g()):>int64 & no_effects=>x',
    'f=(x:int64):>int64 & no_effects=>g(x)\ng=(x:int64):>int64=>{printl("recursive") return f(x)}',
    '$prototype\nf=():>void & no_effects=>printl("observable")',
])
def test_effectful_or_unknown_operations_cannot_claim_empty_row(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_effect_kind_cannot_enter_value_union():
    with pytest.raises(ReportException):
        codegen(SrcFile(None, 'f=():>int64|no_effects=>42'))


def test_callback_contract_and_private_mutation_execute(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/no_effects.dewy'
    execute(tmp_path, 'no-effects', codegen(SrcFile.from_path(fixture)))


def test_subtyping_and_generic_substitution_preserve_empty_row():
    pure = ty.FunctionType([], [], None, 'int64', effects=Contract(Row()))
    unknown = ty.FunctionType([], [], None, 'int64')
    system = ty.TypeSystem()
    assert system.is_subtype(pure, unknown)
    assert not system.is_subtype(unknown, pure)
    generic = ty.FunctionType([], [], None, ty.TypeVariable('T'), [ty.GenericParam('T')], Contract(Row()))
    assert ty.instantiate_method(generic, {'T': 'int64'}).effects == pure.effects
    assert ty.substitute_type(pure, {}).effects == pure.effects


def test_unknown_callback_cannot_be_passed_as_pure():
    source = '''apply=(f:():>int64 & no_effects):>int64 & no_effects=>f()
unknown=():>int64=>{printl("effect") return 42}
main=():>int64=>apply(@unknown)
'''
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))
