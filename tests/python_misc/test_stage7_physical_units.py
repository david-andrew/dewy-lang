import re
from pathlib import Path
from shutil import which

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError, UserError
from dewy.semantic.hir_display import type_alias_value_to_dewy, type_to_dewy
from udewy.frontend import entry_point


def _check(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return root


def _declarations(root: hir.Block) -> dict[str, hir.Declare]:
    return {
        item.name: item
        for item in root.items
        if isinstance(item, hir.Declare)
    }


def test_direct_type_product_constructs_a_quantity_type() -> None:
    root = _check('const Duration:type = int * Time')
    declaration = _declarations(root)['Duration']

    assert isinstance(declaration.expr, hir.TypeValue)
    assert declaration.expr.value == ty.QuantityType(
        'int',
        ty.dimension(('Time', 1)),
    )
    assert type_to_dewy(declaration.expr.value) == 'int * Time'


def test_duration_is_a_bounded_generic_type_alias() -> None:
    root = _check('const Duration:type = <T of real>(T * Time)')
    declaration = _declarations(root)['Duration']

    assert isinstance(declaration.expr, hir.TypeValue)
    assert isinstance(declaration.expr.value, ty.GenericTypeAlias)
    assert declaration.expr.value.params == [ty.GenericParam('T', 'real')]
    assert declaration.expr.value.body == ty.QuantityType(
        ty.TypeVariable('T', 'real'),
        ty.dimension(('Time', 1)),
    )
    assert type_alias_value_to_dewy(declaration.expr.value) == '<T of real>(T * Time)'


@pytest.mark.parametrize('representation', ['int', 'int64', 'uint64', 'float64'])
def test_duration_preserves_its_numeric_representation(representation: str) -> None:
    root = _check(f'''
const Duration:type = <T of real>(T * Time)
let duration:Duration<{representation}> = 1 transmute Duration<{representation}>
''')

    assert _declarations(root)['duration'].annotation == ty.QuantityType(
        representation,
        ty.dimension(('Time', 1)),
    )


def test_duration_rejects_non_real_representations() -> None:
    with pytest.raises(TypeCheckError, match='does not satisfy its bound'):
        _check('''
const Duration:type = <T of real>(T * Time)
let consume = (duration:Duration<string>):>void => void
''')


def test_generic_type_alias_requires_type_arguments() -> None:
    with pytest.raises(TypeCheckError, match='requires arguments'):
        _check('''
const Duration:type = <T of real>(T * Time)
let consume = (duration:Duration):>void => void
''')


def test_generic_type_alias_rejects_wrong_arity() -> None:
    with pytest.raises(UserError, match='wrong number of generic type arguments'):
        _check('''
const Duration:type = <T of real>(T * Time)
let consume = (duration:Duration<int64 uint64>):>void => void
''')


def test_juxtaposition_multiplies_a_number_by_a_typed_unit() -> None:
    root = _check('''
const Duration:type = <T of real>(T * Time)
const ms:Duration<1000000> = 1000000 transmute Duration<1000000>
let delay:Duration<int64> = 300ms
''')
    delay = _declarations(root)['delay'].expr

    assert isinstance(delay, hir.Integer)
    assert delay.type == ty.QuantityType(
        ty.IntegerLiteralType(300000000),
        ty.dimension(('Time', 1)),
    )
    assert delay.value == 300000000


@pytest.mark.parametrize('representation', ['int', 'int64', 'uint64', 'float64'])
def test_unit_multiplication_preserves_variable_representation(
    representation: str,
) -> None:
    root = _check(f'''
let value:{representation} = 2 transmute {representation}
let delay = value * s
''')

    assert _declarations(root)['delay'].expr.type == ty.QuantityType(
        representation,
        ty.dimension(('Time', 1)),
    )


def test_fractional_unit_scales_make_rational_quantities() -> None:
    # `ms` is the exact rational 1/1000 s, so a runtime integer times it is a
    # runtime rational quantity; a literal folds to an exact constant.
    root = _check('let value:int64 = 2 transmute int64\nlet delay = value * ms\nconst pause = 300ms')
    delay_result = _declarations(root)['delay'].expr.type
    assert isinstance(delay_result, ty.TypeOr) and 'Overflow' in delay_result.items  # int64 parts may overflow
    delay = next(item for item in delay_result.items if isinstance(item, ty.QuantityType))
    assert isinstance(delay.number, ty.ObjectType)
    assert delay.dimension == ty.dimension(('Time', 1))
    assert _declarations(root)['pause'].expr.type == ty.QuantityType(
        ty.RationalLiteralType(3, 10),
        ty.dimension(('Time', 1)),
    )


def test_sleep_requires_a_time_quantity() -> None:
    with pytest.raises(UserError, match='type mismatch'):
        codegen(SrcFile(None, 'sleep(300)'))


def test_unit_dimensions_are_erased_from_udewy() -> None:
    emitted = codegen(SrcFile(None, 'sleep(300ms)'))

    assert re.search(r'sleep = \(\w+:int64\):>void', emitted)  # a rational-seconds object
    assert 'ms:int64' not in emitted
    assert '_rational_make(3 10' in emitted  # 300ms is 3/10 s
    assert '__syscall2__(35 request 0)' in emitted
    assert 'Time' not in emitted
    assert 'Duration' not in emitted


@pytest.mark.skipif(
    which('as') is None or which('ld') is None,
    reason='as/ld not available',
)
def test_sleep_compiles_and_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / 'sleep.udewy'
    path.write_text(codegen(SrcFile(None, 'sleep(1ms)')))
    monkeypatch.chdir(tmp_path)

    assert entry_point(path, []) == 0


def test_complete_hero_program_compiles_with_sleep() -> None:
    source = '''
text = "café 👨‍👩‍👧‍👦 🍀"

loop i in 0.. and c in text
    if c not =? ' ' {
        printl"{i}: {c}"
        sleep(300ms)
    }
'''
    emitted = codegen(SrcFile(None, source))

    assert '__syscall2__(35 request 0)' in emitted
    assert '_rational_make(3 10' in emitted
