"""Minted objects carry a brand word: `is?`/`match` on a parent-typed value, `$abstract` parents."""
import pytest

from dewy.reporting import ReportException, SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source))


CONTEXTS = 'Context = $abstract type of any & [depth:int64]\nRoot = type of Context & [base:string="0d"]\nLeaf = type of Context\n'


def test_a_match_over_an_abstract_parent_is_exhaustive_over_its_children() -> None:
    _check(CONTEXTS + 'let k = (c:Context):>int64 => match c { r:Root => r.base.length  <Leaf> => 2 }')


def test_a_missing_child_is_reported() -> None:
    with pytest.raises(UserError, match='`Leaf` \\(a `Context`\\) is not handled'):
        _check(CONTEXTS + 'let k = (c:Context):>int64 => match c { <Root> => 1 }')


def test_a_concrete_parent_needs_its_own_arm() -> None:
    with pytest.raises(UserError, match='`Token` itself'):
        _check('Token = type of any & [idx:int64]\nName = type of Token & [text:string]\nlet k = (t:Token):>int64 => match t { <Name> => 1 }')
    _check('Token = type of any & [idx:int64]\nName = type of Token & [text:string]\nlet k = (t:Token):>int64 => match t { <Name> => 1  <Token> => 0 }')


def test_an_abstract_type_is_not_constructed() -> None:
    with pytest.raises(UserError, match='`Context` is abstract'):
        _check(CONTEXTS + 'let c = Context(depth=1)')
    with pytest.raises(UserError, match='`\\$abstract` marks a `type of` mint'):
        _check('let n:int64 = 3\nlet A = $abstract int64')


def test_a_child_minted_in_another_module_is_caught(tmp_path) -> None:
    (tmp_path / 'ctx.dewy').write_text(CONTEXTS + 'let k = (c:Context):>int64 => match c { <Root> => 1  <Leaf> => 2 }\n')
    (tmp_path / 'main.dewy').write_text('from p"ctx.dewy" import Context, k\nExtra = type of Context\nmain = () => exit(k(Extra(depth=1)))\n')
    with pytest.raises(UserError, match='`Extra` \\(a `Context` minted elsewhere'):
        check.typecheck_and_resolve(SrcFile.from_path(tmp_path / 'main.dewy'))


def test_an_else_takes_children_minted_later(tmp_path) -> None:
    (tmp_path / 'ctx.dewy').write_text(CONTEXTS + 'let k = (c:Context):>int64 => match c { <Root> => 1 } else 0\n')
    (tmp_path / 'main.dewy').write_text('from p"ctx.dewy" import Context, k\nExtra = type of Context\nmain = () => exit(k(Extra(depth=1)))\n')
    check.typecheck_and_resolve(SrcFile.from_path(tmp_path / 'main.dewy'))
