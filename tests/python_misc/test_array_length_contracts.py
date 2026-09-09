"""Length-changing methods preserve both ends of an array's store contract."""

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError


def compile_body(body):
    return codegen(SrcFile(None, f'let main = ():>int64 => {{ {body}\nreturn 0 }}'))


@pytest.mark.parametrize('method', ['push(3)', 'insert(3 1)'])
def test_growth_cannot_exceed_a_declared_maximum(method):
    with pytest.raises(UserError, match='keeps its declared length'):
        compile_body(f'let xs:array<int64 length <=? 2> = [1 2]\nxs.{method}')
    compile_body(f'let xs:array<int64 length <=? 3> = [1 2]\nxs.{method}')


@pytest.mark.parametrize('method', ['pop;', 'truncate(0)', 'clear'])
def test_shrinking_cannot_cross_a_declared_minimum(method):
    with pytest.raises(UserError, match='keeps its declared length'):
        compile_body(f'let xs:array<int64 length >=? 1> = [1]\nxs.{method}')


def test_guarded_growth_and_shrink_preserve_parameter_contracts():
    codegen(SrcFile(None, '''
let append = (@xs:array<int64 length <=? 3>):>void => {
    if xs.length <? 3 { xs.push(9) }
}
let remove = (@xs:array<int64 length >=? 1>):>void => {
    if xs.length >? 1 { xs.pop; }
}
'''))


@pytest.mark.parametrize('contract, initial, method', [
    ('length <=? 2', '[1 2]', 'push(3)'),
    ('length >=? 1', '[1]', 'clear'),
])
def test_array_fields_keep_their_length_contract(contract, initial, method):
    source = f'let Bag:type = [items:array<int64 {contract}>]\nlet bag:Bag = [items={initial}]\nbag.items.{method}'
    with pytest.raises(UserError, match='keeps its declared length'):
        compile_body(source)


def test_assignment_keeps_a_maximum_available_for_later_growth():
    codegen(SrcFile(None, '''
let grow = (incoming:array<int64 length <=? 2>):>void => {
    let xs:array<int64 length <=? 3> = []
    xs = incoming
    xs.push(9)
}
'''))
