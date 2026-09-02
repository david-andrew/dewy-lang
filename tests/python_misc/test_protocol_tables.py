"""Implicit declarations defer like `let` ones; methods fill inherited function slots."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import TypeCheckError


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source))


def test_a_function_declared_bare_may_call_one_written_after_it() -> None:
    _check('go = (n:int64):>int64 => later(n) + 1\nlater = (n:int64):>int64 => n * 2')
    _check('let go = (n:int64):>int64 => later(n) + 1\nlater = (n:int64):>int64 => n * 2')


def test_a_second_bare_assignment_in_a_block_still_assigns() -> None:
    _check('main = () => {\n    x = 1\n    x = 2\n    exit(x)\n}')
    with pytest.raises(TypeCheckError, match="type mismatch"):
        _check('main = () => {\n    x = 1\n    x = "two"\n    exit(x)\n}')


def test_a_method_named_like_an_inherited_function_field_fills_it() -> None:
    _check(
        'let P:type = [eat:<(n:int64):>int64> extra:int64 = 0]\n'
        'Ws = type of P & [eat = (n:int64):>int64 => n + 1]\n'
        'let a = Ws()\nlet b:P = Ws\nlet c:array<P> = [Ws]\nlet r:int64 = a.eat(1) + b.eat(2) + c[0].extra'
    )


def test_a_mint_with_a_required_field_is_not_a_value() -> None:
    with pytest.raises(TypeCheckError, match="type mismatch"):
        _check('let P:type = [eat:<(n:int64):>int64> extra:int64]\nWs = type of P & [eat = (n:int64):>int64 => n + 1]\nlet b:P = Ws')


def test_function_fields_print_as_their_type() -> None:
    _check('let P:type = [eat:<(n:int64):>int64>]\nlet p:P = [eat = (n:int64):>int64 => n]\nlet s:string = "{p}"')
