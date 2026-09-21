from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic import effect_rows as rows, ty
from tests.python_misc.test_generics import _declared
from tests.python_misc.test_scalar_projection import execute

APPLY = 'let apply=<E:Effect>(f:():>int64 & E):>int64 & E=>f()\n'


@pytest.mark.parametrize('row', ['no_effects', 'reads<Filesystem>', 'no reads<Filesystem>'])
def test_infer_effect_argument_without_creating_a_value_type(row):
    declared = _declared('Filesystem=type of any\n' + APPLY + f'answer=():>int64 & {row}=>42\nmain=():>int64=>apply(@answer)')
    generic = declared['apply'].expr
    parameter = generic.type.type_params[0]
    assert parameter.kind == 'effect'
    instances = [value.expr for key, value in declared.items() if key.startswith('apply__')]
    assert len(instances) == 1
    assert instances[0].type.type_params == []
    assert instances[0].type.effects.allowed is not None
    assert instances[0].type.effects.allowed.variables == ()
    if row.startswith('no reads'):
        assert instances[0].type.effects.allowed.unknown


def test_rows_are_part_of_instance_identity():
    declared = _declared('Filesystem=type of any\n' + APPLY + '''
quiet=():>int64 & no_effects=>42
reader=():>int64 & reads<Filesystem>=>42
main=():>int64=>{let a=apply(@quiet) let b=apply(@reader) let c=apply(@quiet) return c}
''')
    instances = [value.expr for key, value in declared.items() if key.startswith('apply__')]
    assert len(instances) == 2
    assert len({rows.identity(instance.type.effects) for instance in instances}) == 2


@pytest.mark.parametrize('source', [
    'let bad=<E:Effect>(x:E):>int64=>42',
    'let bad=<E:Effect>(x:array<E>):>int64=>42',
    'let bad=<E:Effect>(f:():>int64 & E):>E=>f()',
    'let bad=<E:Effect>(f:():>int64 & E):>int64 & no E=>f()',
    APPLY.replace('=>f()', '=>E') + 'answer=():>int64 & no_effects=>42\nmain=():>int64=>apply(@answer)',
])
def test_effect_rows_cannot_be_value_types_or_values(source):
    with pytest.raises(ReportException, match='effect row|row parameter|value type'):
        codegen(SrcFile(None, source))


def test_unknown_callback_row_is_not_inferred_empty():
    source = APPLY + 'unknown=(f:():>int64):>int64 & no_effects=>apply(@f)\nmain=():>int64=>42'
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_row_inference_joins_repeated_callback_constraints():
    variable = rows.Contract(rows.Row(variables=('E:1',)))
    fs = rows.Atom('reads', rows.Subject('resource', 'Filesystem'))
    db = rows.Atom('mutates', rows.Subject('resource', 'Database'))
    inferred = {}
    assert rows.infer(variable, rows.Contract(rows.Row((fs,))), {'E:1'}, inferred)
    assert rows.infer(variable, rows.Contract(rows.Row((db,))), {'E:1'}, inferred)
    assert inferred['E:1'] == rows.Contract(rows.union(rows.Row((fs,)), rows.Row((db,))))
    assert rows.infer(variable, None, {'E:1'}, inferred)
    assert inferred['E:1'].allowed.unknown
    # A slot belongs to its callback signature, not to the enclosing one.
    assert not rows.infer(variable, rows.Contract(rows.Row((rows.Atom('reads', rows.Subject('parameter', '0')),))), {'E:1'}, {})


def test_native_effect_generic_fixture_executes(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/effect_generics.dewy'
    execute(tmp_path, 'effect-generics', codegen(SrcFile.from_path(fixture)))
