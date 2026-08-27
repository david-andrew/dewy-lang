"""`join` on string arrays and the checked UTF-8 decode `bytes as string | undefined`."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import TypeCheckError, UserError


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source))


def test_join_accepts_any_string_array_and_is_not_a_mutation() -> None:
    _check('let words:array<string length=2> = ["a" "b"]\nlet main = ():>int64 => words.join.length\n')
    _check('let main = ():>int64 => {\n    let ws:array<string> = ["a"]\n    let n:int64 = 0\n    loop w in ws { n += ws.join.length }\n    return n\n}\n')


def test_join_requires_string_elements() -> None:
    with pytest.raises(UserError, match='`join` requires string elements'):
        _check('let xs:array<int64> = [1 2]\nlet main = ():>int64 => xs.join.length\n')


def test_unchecked_decode_still_needs_a_proof_and_points_at_the_checked_form() -> None:
    with pytest.raises(TypeCheckError, match='string conversion requires a validity proof') as caught:
        _check('let raw:array<uint8> = [104]\nlet main = ():>int64 => (raw as string).length\n')
    assert 'as string | undefined' in str(caught.value)


def test_checked_decode_types_as_an_optional_string() -> None:
    emitted = codegen(SrcFile(None, 'let main = ():>int64 => {\n    let s = 0x"6869" as string|undefined\n    if s is? string { return s.length }\n    return 0\n}\n'))
    assert '_arena_alloc' in emitted


def test_joined_strings_can_be_returned() -> None:
    emitted = codegen(SrcFile(None, 'let render = (xs:array<string>):>string => xs.join", "\nlet main = ():>int64 => {\n    let s = render(["a" "b"])\n    return s.length\n}\n'))
    assert 'let render' in emitted
