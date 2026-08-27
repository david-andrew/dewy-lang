"""Growable arrays of objects: arena-backed element copies, and read-only borrowed loop variables."""

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import NotImplementedYet, UserError

SPAN = 'let Span:type = [start:int64 stop:int64 tags:array<int64>]\n'


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def test_object_arrays_grow_return_and_iterate() -> None:
    emitted = _compile(
        SPAN
        + 'let make = (n:int64):>array<Span> => { let xs:array<Span> = []  let i:int64 = 0  loop i <? n { xs.push([start=i stop=i tags=[]])  i += 1 }  return xs }\n'
        + 'let main = ():>int64 => { let xs:array<Span> = make(3)  xs.insert([start=9 stop=9 tags=[]] 0)  let last:Span = xs.pop  let total:int64 = 0  loop s in xs { total += s.start }  return total + last.start }\n'
    )
    assert '_arena_alloc' in emitted  # element copies outlive the frame


def test_loop_variable_over_objects_is_a_read_only_borrow() -> None:
    body = 'let main = ():>int64 => { let xs:array<Span> = []  xs.push([start=1 stop=2 tags=[]])  loop s in xs { %s }  return 0 }\n'
    for statement, title in [
        ('s.start = 5', 'cannot mutate a field of a const object'),
        ('s.tags.push(1)', 'cannot mutate a field of a const binding'),
        ('s = [start=0 stop=0 tags=[]]', 'cannot assign to a read-only binding'),
        ('bump(@s)', 'cannot assign to a read-only binding'),
    ]:
        with pytest.raises(UserError, match=title) as info:
            _compile(SPAN + 'let bump = (@s:Span):>void => { s.start = s.start + 1  return void }\n' + body % statement)
        assert 'borrows the array element' in str(info.value)
    # copying the element gives an independent, mutable value
    _compile(SPAN + body % 'let mine:Span = s  mine.start = 40')


def test_exact_array_fields_inside_growable_object_elements_are_not_supported_yet() -> None:
    with pytest.raises(NotImplementedYet, match='arena-backed copy of an exact-length array'):
        _compile(
            'let Pair:type = [values:array<int64 length=2>]\n'
            'let main = ():>int64 => { let xs:array<Pair> = []  xs.push([values=[1 2]])  return 0 }\n'
        )
