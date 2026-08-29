"""`match`: patterns are signatures; the chain must be total; arms must be reachable."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import TypeCheckError, UserError


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


UNION = 'let f = (v:int64|string|bool):>int64 => '


def test_non_exhaustive_match_names_the_unhandled_member() -> None:
    with pytest.raises(UserError, match=r'match is not exhaustive') as info:
        _compile(UNION + 'match v { n:int64 => n  s:string => s.length }\n')
    assert '`bool` is not handled' in str(info.value)
    _compile(UNION + 'match v { n:int64 => n  s:string => s.length } else 0\n')
    _compile(UNION + 'match v { n:int64 => n  other => 0 }\n')


def test_guards_cover_finite_types_and_name_missing_values() -> None:
    _compile('let g = (s:-1|0|1):>int64 => match s { a:int64<a <? 0> => 1  b:int64<b >=? 0> => 2 }\n')
    with pytest.raises(UserError, match=r'match is not exhaustive') as info:
        _compile('let g = (s:-1|0|1):>int64 => match s { a:int64<a <? 0> => 1  b:int64<b >? 0> => 2 }\n')
    assert 'value `0`' in str(info.value)
    # an unbounded integer needs a catch-all or a covering guard set
    with pytest.raises(UserError, match=r'match is not exhaustive'):
        _compile('let g = (n:int64):>int64 => match n { a:int64<a <? 100> => 1 }\n')
    _compile('let g = (n:int64):>int64 => match n { a:int64<a <? 100> => 1  b:int64<b >=? 100> => 2 }\n')


def test_unreachable_arms_are_errors() -> None:
    with pytest.raises(UserError, match=r'unreachable match arm'):
        _compile(UNION + 'match v { any => 0  n:int64 => n }\n')
    with pytest.raises(UserError, match=r'unreachable match arm'):
        _compile('let g = (n:int64):>int64 => match n { <5> => 1  <5> => 2  other => 3 }\n')


def test_bare_names_are_catch_alls_and_warn_unless_underscore(capsys) -> None:
    # `_` is the idiomatic catch-all; any other bare name binds the whole value (shadowing, as a parameter would) and warns
    _compile('let E:type = type of error\nlet f = (v:int64|E):>int64 => match v { n:int64 => n  _ => 0 }\n')
    assert 'bare name' not in capsys.readouterr().err
    _compile('let E:type = type of error\nlet f = (v:int64|E):>int64 => match v { n:int64 => n  E => 0 }\n')
    err = capsys.readouterr().err
    assert 'bare name in a match arm binds the whole value' in err and '`_`' in err
