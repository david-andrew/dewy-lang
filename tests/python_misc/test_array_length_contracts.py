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


def test_pop_retains_a_stronger_index_bound():
    codegen(SrcFile(None, '''
let read_after_pop = (@xs:array<int64> i:addr):>int64 => {
    if xs.length >? 1 and i <? xs.length-1 {
        xs.pop;
        return xs[i]
    }
    return 0
}
'''))


def test_runtime_truncation_count_needs_a_nonnegative_proof():
    source = 'let shorten = (@xs:array<int64> count:int64):>void => { BODY }'
    with pytest.raises(UserError, match='truncate length is not proven nonnegative'):
        codegen(SrcFile(None, source.replace('BODY', 'xs.truncate(count)')))
    codegen(SrcFile(None, source.replace('BODY', 'if count >=? 0 { xs.truncate(count) }')))


@pytest.mark.parametrize('body', ['xs.push(1)', 'xs.insert(1 0)'])
def test_growth_keeps_a_length_contract_relative_to_another_array(body):
    source = 'let grow = (limit:array<int64> @xs:array<int64 length <=? limit.length>):>void => { BODY }'
    with pytest.raises(UserError, match='keeps its declared length'):
        codegen(SrcFile(None, source.replace('BODY', body)))
    codegen(SrcFile(None, source.replace('BODY', f'if xs.length <? limit.length {{ {body} }}')))


def test_shrinking_transforms_relative_length_contracts():
    upper = 'let shrink = (limit:array<int64> @xs:array<int64 length <=? limit.length>):>void => { BODY }'
    codegen(SrcFile(None, upper.replace('BODY', 'xs.truncate(2) xs.clear')))
    lower = 'let shrink = (limit:array<int64> @xs:array<int64 length >=? limit.length>):>void => { BODY }'
    with pytest.raises(UserError, match='keeps its declared length'):
        codegen(SrcFile(None, lower.replace('BODY', 'if xs.length >? 0 { xs.pop; }')))
    codegen(SrcFile(None, lower.replace('BODY', 'if xs.length >? limit.length { xs.pop; }')))


def test_unequal_runtime_lengths_do_not_imply_nonempty():
    with pytest.raises(UserError, match='non-empty'):
        codegen(SrcFile(None, '''
let remove = (@xs:array<int64> other:array<int64>):>void => {
    if xs.length not=? other.length { xs.pop; }
}
'''))


def test_unsupported_prototype_mutation_check_stays_a_compile_error():
    with pytest.raises(UserError, match='truncate length is not proven nonnegative'):
        codegen(SrcFile(None, '''$prototype
let shorten = (@xs:array<int64> count:int64):>void => { xs.truncate(count) }
'''))
