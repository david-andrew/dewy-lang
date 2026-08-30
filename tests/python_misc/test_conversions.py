"""The conversion protocol: a type's `__as__ = ():>T => …` method serves `x as T` and string interpolation."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import TypeCheckError, UserError


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


POINT = 'let Point:type = [x:int64 y:int64 __as__ = ():>string => "({x}, {y})"]\n'


def test_as_and_interpolation_call_the_conversion_method() -> None:
    emitted = _compile(POINT + 'let main = ():>int64 => { let pt = Point(3 4)  let s:string = pt as string  printl"{pt}"  return s.length }\n')
    assert emitted.count('Point____as__') >= 2   # one call for `as`, one for the interpolation field


def test_paths_convert_through_the_same_protocol() -> None:
    # nothing about `Path` is special: it declares `__as__ = ():>string => path`
    emitted = _compile('let main = ():>int64 => { let file = p"a/b.c"  let t:string = file.parent as string  return "{file.parent}/{file.stem}".length + t.length }\n')
    assert 'Path____as__' in emitted


def test_objects_without_a_conversion_are_rejected() -> None:
    with pytest.raises(TypeCheckError, match='no string conversion for this interpolation field'):
        _compile('let Pair:type = [a:int64 b:int64]\nlet main = ():>int64 => { let q = Pair(1 2)  printl"{q}"  return 0 }\n')
    with pytest.raises(TypeCheckError, match='unsupported value conversion'):
        _compile('let Pair:type = [a:int64 b:int64]\nlet main = ():>int64 => { let q = Pair(1 2)  let s:string = q as string  return s.length }\n')
    # a conversion to another target does not serve `string`
    with pytest.raises(TypeCheckError, match='unsupported value conversion'):
        _compile('let Wrap:type = [v:int64 __as__ = ():>int64 => v]\nlet main = ():>int64 => { let w = Wrap(1)  let s:string = w as string  return s.length }\n')


def test_conversion_methods_take_no_arguments() -> None:
    with pytest.raises(UserError, match='`__as__` takes no arguments'):
        _compile('let Wrap:type = [v:int64 __as__ = (n:int64):>string => "x"]\nlet main = ():>int64 => { let w = Wrap(1)  return "{w}".length }\n')
