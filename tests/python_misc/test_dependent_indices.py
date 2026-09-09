"""Index contracts refer to a sequence's current value, including place results."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import TypeCheckError, UserError

APPEND = '''
let append = <T>(@xs:array<T> value:T):>addr<i => i <? xs.length> => {
    let i = xs.length
    xs.push(value)
    return i
}
let at = <T>(xs:array<T> i:addr<v => v <? xs.length>):>T => xs[i]
'''


def compile_body(body: str) -> str:
    return codegen(SrcFile(None, APPEND + '\nf = (source:array<int64> other:array<int64>):>int64 => {\n'
                           'let xs:array<int64> = source\n' + body + '\n}'))


@pytest.mark.parametrize('body', [
    'let i = append(@xs 42) return xs[i]',
    'let i = append(@xs 42) return at(xs i)',
    'let i = append(@xs 42) xs.push(2) return xs[i]',
    'let i = append(@xs 42) xs[i] = 2 return xs[i]',
    'let i = append(@xs 42) let copy = xs xs.clear return copy[i]',
])
def test_append_proves_an_index_and_preserving_operations_keep_it(body):
    compile_body(body)


@pytest.mark.parametrize('body', [
    'let i = append(@xs 42) return other[i]',
    'let i = append(@xs 42) xs.clear return xs[i]',
    'let i = append(@xs 42) xs.truncate(0) return xs[i]',
    'let i = append(@xs 42) xs = other return xs[i]',
    'let i = append(@xs 42) xs = other return at(xs i)',
    'let i = append(@xs 42) if xs.length =? 0 return 0 let removed = xs.pop return xs[i]',
])
def test_an_index_cannot_outlive_its_length_evidence(body):
    with pytest.raises((UserError, TypeCheckError), match='not proven|cannot prove refinement|refinement refuted'):
        compile_body(body)


def test_place_call_invalidates_old_evidence_before_its_result_is_used():
    source = '''
clear = (@xs:array<int64>):>void => { xs.clear }
f = (xs:array<int64>):>int64 => {
    if xs.length =? 0 return 0
    clear(@xs)
    return xs[0]
}
'''
    with pytest.raises(UserError, match='not proven'):
        codegen(SrcFile(None, source))


def test_push_does_not_preserve_a_stale_upper_bound_on_length():
    with pytest.raises(UserError, match='cannot prove refinement|refinement refuted'):
        codegen(SrcFile(None, '''
f = (@xs:array<int64>):>addr<i => i >=? xs.length> => {
    let old = xs.length
    xs.push(1)
    return old
}
'''))


def test_literal_argument_obligation_substitutes_the_callers_sequence():
    codegen(SrcFile(None, APPEND + '\nf = ():>int64 => { let xs:array<int64> = [42] return at(xs 0) }'))


@pytest.mark.parametrize('change', ['xs.clear', 'xs = other', 'xs.truncate(0)'])
@pytest.mark.parametrize('read', ['xs[i]', 'at(xs i)'])
def test_declared_index_contract_expires_when_its_term_changes(change, read):
    with pytest.raises((UserError, TypeCheckError), match='not proven|cannot prove refinement|refinement refuted'):
        compile_body(f'''if xs.length =? 0 return 0
            let i:addr<v => v <? xs.length> = 0
            {change}
            return {read}''')


def test_declared_dependent_index_can_be_used_before_a_later_mutation():
    compile_body('''if xs.length =? 0 return 0
        let i:addr<v => v <? xs.length> = 0
        let result = xs[i]
        xs.clear
        return result''')


def test_place_parameters_keep_their_declared_scalar_contract_when_forwarded():
    codegen(SrcFile(None, '''
step = (@position:addr):>void => { position += 1 }
forward = (@position:addr):>void => { position += 1 step(@position) }
main = ():>int64 => { let position:addr = 0 forward(@position) return position }
'''))


@pytest.mark.parametrize('write', ['position = -1', 'position -= 1'])
def test_place_parameter_writes_must_preserve_the_callers_scalar_contract(write):
    with pytest.raises((UserError, TypeCheckError), match='cannot prove|refinement refuted'):
        codegen(SrcFile(None, f'step = (@position:addr):>void => {{ {write} }}'))


def test_affine_assignment_keeps_the_same_length_relation_as_combined_assignment():
    codegen(SrcFile(None, '''
end = (xs:array<int64>):>addr<i => i <=? xs.length> => {
    let i:addr = 0
    loop i <? xs.length { i = i + 1 }
    return i
}
'''))
    with pytest.raises(UserError, match='not proven'):
        compile_body('let i:addr = 0 loop i <? xs.length { i = i + 1 } return xs[i]')
