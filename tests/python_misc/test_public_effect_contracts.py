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


@pytest.mark.parametrize('source', [
    'Filesystem=type of any\nf=():>int64 & reads<Filesystem>=>42',
    'Filesystem=type of any\nf=(callback:():>int64 & reads<Filesystem>):>int64 & reads<Filesystem>=>callback()',
    'Filesystem=type of any\nf=(callback:():>int64 & no reads<Filesystem>):>int64 & no reads<Filesystem>=>callback()',
    'Filesystem=type of any\nf=(callback:():>int64 & no reads):>int64 & no reads<Filesystem>=>callback()',
    'Filesystem=type of any\nDatabase=type of any\nf=(callback:():>int64 & reads<Database>):>int64 & no reads<Filesystem>=>callback()',
    'f=(@x:int64):>int64 & reads<x>=>x',
    'f=(@x:int64):>void & mutates<x>=>{x=42}',
    'f=(@x:int64):>void & reads<x> & mutates<x>=>{x+=1}',
    'g=(@x:int64):>int64=>x\nf=(@y:int64):>int64 & reads<y>=>g(@y)',
    'g=(@x:int64):>void=>{x=42}\nf=():>int64 & no_effects=>{let y:int64=0 g(@y) return y}',
    'g=(@x:int64):>int64=>x\nf=(@r:[value:int64]):>int64 & reads<r.value>=>g(@r.value)',
    'f=(callback:(@v:int64):>int64 & reads<v> @x:int64):>int64 & reads<x>=>callback(@x)',
    'f=(callback:(@v:int64):>void & mutates<v> @x:int64):>void & mutates<x>=>callback(@x)',
    'f=():>int64 & no reads=>42',
    'f=():>no_effects & int64=>42',
])
def test_named_effects_and_place_translation(source):
    codegen(SrcFile(None, source))


@pytest.mark.parametrize('source', [
    'Filesystem=type of any\nf=(callback:():>int64 & reads<Filesystem>):>int64 & no_effects=>callback()',
    'Filesystem=type of any\nf=(callback:():>int64 & no reads<Filesystem>):>int64 & no_effects=>callback()',
    'Filesystem=type of any\nf=(callback:():>int64):>int64 & no reads<Filesystem>=>callback()',
    'Filesystem=type of any\nDatabase=type of any\nf=(callback:():>int64 & reads<Database>):>int64 & reads<Filesystem>=>callback()',
    'f=(@x:int64):>void & mutates<x>=>{x+=1}',
    'g=(@x:int64):>void=>{x=42}\nf=(@y:int64):>void & reads<y>=>g(@y)',
    'f=(@r:[left:int64 right:int64]):>int64 & reads<r.left>=>r.right',
    'g=(@x:int64):>int64=>x\nf=(@r:[left:int64 right:int64]):>int64 & reads<r.left>=>g(@r.right)',
])
def test_named_effects_do_not_grant_other_authority(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


@pytest.mark.parametrize('annotation,message', [
    ('reads<>', 'empty effect family'), ('no reads<>', 'empty effect family'),
    ('reads', 'positive effect needs a resource'),
    ('reads<int64>', 'nominal identity'), ('reads<x>', 'caller-owned storage'),
    ('no no_effects', 'cannot exclude an empty'), ('no Effect<>', 'cannot exclude an empty'),
])
def test_malformed_effect_subjects(annotation, message):
    with pytest.raises(ReportException, match=message):
        codegen(SrcFile(None, f'f=(x:int64):>int64 & {annotation}=>42'))


def test_imported_nominal_effects_and_scalar_places_execute(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/named_effects.dewy'
    execute(tmp_path, 'named-effects', codegen(SrcFile.from_path(fixture)))


@pytest.mark.parametrize('name', ['effect_identity_rejected', 'effect_exclusion_rejected'])
def test_effect_fixture_rejections(name):
    fixture = Path(__file__).resolve().parents[1] / f'fixtures/{name}.dewy'
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile.from_path(fixture))


def test_callable_display_keeps_permissions_and_exclusions():
    from dewy.semantic.effect_rows import Atom, Subject
    from dewy.semantic.hir_display import type_to_dewy
    contract = Contract(Row((Atom('reads', Subject('resource', 'Filesystem')),)),
                        (Atom('mutates', Subject('parameter', '0', ('value',))),))
    signature = ty.FunctionType([ty.PosOrKwArg('state', 'int64', place=True)], [], None, 'int64', effects=contract)
    text = type_to_dewy(signature)
    assert 'reads<Filesystem>' in text
    assert 'no mutates<state.value>' in text


@pytest.mark.parametrize('permission,accepts', [('x', True), ('y', False)])
def test_hidden_method_receiver_does_not_change_effect_slots(permission, accepts):
    source = f'''Box=type of [base:int64 set=(@x:int64 @y:int64):>void & mutates<{permission}>=>{{x=base}}]
main=():>int64=>{{let box=Box[42] let x:int64=0 let y:int64=0 box.set(@x @y) return x}}
'''
    if accepts:
        codegen(SrcFile(None, source))
    else:
        with pytest.raises(ReportException, match='effect contract'):
            codegen(SrcFile(None, source))


@pytest.mark.parametrize('source', ['f=(<@x:int64>):>int64 & reads<x>=>x', 'let x=no true', 'T:type=no int64'])
def test_position_only_effects_and_effect_only_prefix(source):
    if source.startswith('f='):
        codegen(SrcFile(None, source))
    else:
        with pytest.raises(ReportException, match='only an effect exclusion'):
            codegen(SrcFile(None, source))
