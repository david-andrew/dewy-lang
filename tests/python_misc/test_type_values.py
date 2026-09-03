"""Types as first-class values (`type<T>`, `typeof`), and static methods."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import TypeCheckError, UserError


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source))


FAMILY = 'Token = $abstract type of any & [idx:int64  eat:<(n:int64):>int64>  width = ():>int64 => idx * 2]\nWs = type of Token & [eat = (n:int64):>int64 => n + 1]\nLc = type of Token & [eat = (n:int64):>int64 => n + 2]\n'


def test_a_type_value_is_stored_compared_and_matched() -> None:
    _check(FAMILY + 'let kinds:array<type<Token>> = [Ws Lc]\nlet k:type<Token> = Ws\nlet a:bool = k =? Ws and k not=? Lc and k is? Ws\nlet f = (t:type<Token>):>int64 => match t { <Ws> => 1  <Lc> => 2 }\nlet s:string = k.typename')


def test_typeof_reads_the_brand_and_a_type_value_constructs() -> None:
    _check(FAMILY + 'let tok = Ws(idx=1)\nlet k = typeof(tok)\nlet ok:bool = k =? Ws\nlet t:Token = tok\nlet again:Token = typeof(t)(idx=2)')


def test_static_methods_are_called_off_the_type_and_dispatched_by_type_value() -> None:
    _check(FAMILY + 'let a:int64 = Ws.eat(1)\nlet k:type<Token> = Lc\nlet b:int64 = k.eat(1)\nlet c:int64 = Ws(idx=0).eat(1)')


def test_an_instance_method_is_not_callable_off_the_type() -> None:
    with pytest.raises(TypeCheckError, match='`width` needs an instance'):
        _check(FAMILY + 'let w:int64 = Ws.width')


def test_a_type_outside_the_family_is_rejected() -> None:
    with pytest.raises(TypeCheckError, match='type value outside its family'):
        _check(FAMILY + 'Other = type of any & [x:int64]\nlet k:type<Token> = Other')


def test_a_match_over_type_values_must_cover_the_family() -> None:
    with pytest.raises(UserError, match='match is not exhaustive'):
        _check(FAMILY + 'let f = (t:type<Token>):>int64 => match t { <Ws> => 1 }')


def test_static_transitively_through_static_calls() -> None:
    _check('P = type of any & [x:int64  a = (n:int64):>int64 => b(n) + 1  b = (n:int64):>int64 => n * 2]\nlet r:int64 = P.a(3)')
    with pytest.raises(TypeCheckError, match='`a` needs an instance'):
        _check('P = type of any & [x:int64  a = (n:int64):>int64 => b(n) + 1  b = (n:int64):>int64 => n * x]\nlet r:int64 = P.a(3)')


def test_mints_may_refer_to_each_other_forwards_and_through_function_types() -> None:
    _check('Opener = type of any & [closer:Closer? = none]\nCloser = type of any & [opener:Opener? = none]\nlet o = Opener(closer=Closer())')
    _check('Ctx = $abstract type of any & [previous:Tok?]\nlet eatfn:type = (c:Ctx):>int64?\nTok = type of any & [eat:eatfn]\nlet f = (c:Ctx):>int64 => 1')


def test_a_self_referencing_mint_field_still_needs_a_union() -> None:
    with pytest.raises(UserError, match='refers to itself without a union'):
        _check('Node = type of any & [next:Node]')


def test_type_values_print_as_their_names() -> None:
    _check('T = $abstract type of any & [x:int64]\nKind = type of T\nlet kinds:array<type<T>> = [Kind]\nlet s:string = "{kinds} {kinds[0]}"\nlet k:type<T> = Kind\nlet t:string = k as string')
