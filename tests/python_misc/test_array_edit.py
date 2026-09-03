import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import NotImplementedYet, UserError
from dewy.backend.udewy import codegen


def _check(body: str):
    return check.typecheck_and_resolve(SrcFile(None, f'let main = ():>int64 => {{\n{body}\n    return 0\n}}'))


def test_constant_indexes_are_proven_against_the_exact_length() -> None:
    _check('    let xs:array<int64> = [1 2 3]\n    xs.insert(9 3)\n    let a = xs.pop(3)\n    xs.truncate(1)')


def test_constant_pop_index_out_of_bounds() -> None:
    with pytest.raises(UserError, match='pop index is out of bounds'):
        _check('    let xs:array<int64> = [1 2 3]\n    let a = xs.pop(3)')


def test_constant_insert_index_past_the_end() -> None:
    with pytest.raises(UserError, match='insert index is out of bounds'):
        _check('    let xs:array<int64> = [1 2 3]\n    xs.insert(9 4)')


def test_runtime_index_needs_a_proof() -> None:
    with pytest.raises(UserError, match='`pop` index is not proven in bounds'):
        codegen(SrcFile(None, (
            'let main = (args:array<string>):>int64 => {\n'
            '    let xs:array<int64> = [1 2 3]\n'
            '    let idx:int64 = args.length\n'
            '    let a = xs.pop(idx)\n'
            '    return a\n}'
        )))


def test_runtime_index_is_proven_by_a_guard() -> None:
    emitted = codegen(SrcFile(None, (
        'let main = (args:array<string>):>int64 => {\n'
        '    let xs:array<int64> = [1 2 3]\n'
        '    let idx:int64 = args.length\n'
        '    if idx <? xs.length { xs.insert(7 idx) let a = xs.pop(idx) return a }\n'
        '    return 0\n}'
    )))
    assert 'shift' in emitted


def test_truncate_resets_index_proofs_and_negative_counts_are_rejected() -> None:
    with pytest.raises(UserError, match='truncate length cannot be negative'):
        _check('    let xs:array<int64> = [1 2 3]\n    xs.truncate((-1))')
    with pytest.raises(UserError, match='out of bounds|not proven'):
        _check('    let xs:array<int64> = [1 2 3]\n    xs.truncate(1)\n    let a = xs[2]')


def test_sort_keeps_length_facts() -> None:
    _check('    let xs:array<int64> = [3 1 2]\n    xs.sort\n    let a = xs[2]\n    let b = xs.pop')


def test_sort_of_non_integer_elements_needs_a_key() -> None:
    with pytest.raises(UserError, match='sorting these elements needs a key'):
        _check('    let xs:array<string> = ["b" "a"]\n    xs.sort')
    _check('    let xs:array<string> = ["b" "a"]\n    xs.sort(key=(s) => s.length)')


def _check_bag(body: str):
    return check.typecheck_and_resolve(SrcFile(None, (
        'let Bag:type = [items:array<int64> total:int64]\n'
        f'let main = ():>int64 => {{\n    let bag:Bag = [items = [1 2 3] total = 0]\n{body}\n    return 0\n}}'
    )))


def test_member_route_facts_prove_indexes_and_methods() -> None:
    _check_bag('    bag.items.push(4)\n    let a = bag.items[3]\n    let b = bag.items.pop\n    bag.items.insert(9 3)')


def test_assigning_the_root_drops_member_route_facts() -> None:
    with pytest.raises(UserError, match='index is not proven'):
        _check_bag('    let other:Bag = [items = [1] total = 0]\n    bag = other\n    let a = bag.items[2]')


def test_assigning_the_field_drops_member_route_facts() -> None:
    with pytest.raises(UserError, match='index is not proven'):
        _check_bag('    bag.items = [1]\n    let a = bag.items[2]')
    with pytest.raises(UserError, match='empty array|non-empty'):
        _check_bag('    bag.items = []\n    bag.items.clear\n    let a = bag.items.pop')
