"""Errors carrying fields are minted objects in the `error` family."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, ty
from dewy.semantic.errors import NotImplementedYet, UserError


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source))


def test_an_error_with_fields_is_constructed_matched_and_read() -> None:
    _check(
        'let Bad = type of error & [code:int64 note:string = "none"]\n'
        'let f = (n:int64):>int64 | Bad => if n <? 0 Bad(code=n) else n\n'
        'let g = (n:int64):>int64 => match f(n) { b:Bad => b.code  v:int64 => v }'
    )


def test_an_error_with_fields_is_in_the_error_family() -> None:
    _check(
        'let Bad = type of error & [code:int64]\n'
        'let f = (n:int64):>int64 | Bad => if n <? 0 Bad(code=n) else n\n'
        'let g = (n:int64):>int64 => match f(n) { e:error => 0  v:int64 => v }\n'
        'let h = (n:int64):>int64 | Bad => { let v:int64 = f(n) or_throw  return v }'
    )
    checker = ty.TypeSystem()
    checker.register_user_nominals()
    bad = ty.ObjectType((ty.ObjectField('code', 'int64', True, None, ()),), brand='Bad')
    assert checker.is_subtype(bad, 'error') and checker.is_subtype(bad, ty.EXCEPTION_TYPE)
    assert not checker.is_subtype(bad, 'object')


def test_a_minted_object_satisfies_its_structure() -> None:
    _check(
        'let Info:type = [title:string code:int64]\n'
        'let Tagged = type of any & Info\n'
        'let n = (r:Info):>int64 => r.code\n'
        'let m = n(Tagged(title="a" code=1))'
    )


def test_a_child_of_an_error_with_fields_is_one_too() -> None:
    _check(
        'let Bad = type of error & [code:int64]\n'
        'let Worse = type of Bad & [why:string]\n'
        'let w = Worse(code=1 why="x")\n'
        'let ok:bool = w is? Bad and w is? error'
    )


def test_a_child_stored_as_its_parent_union_member_is_a_target_diagnostic() -> None:
    from dewy.backend.udewy import codegen
    with pytest.raises(NotImplementedYet, match='a `Name` value stored as the `Token` member of a union'):
        codegen(SrcFile(None, 'let Token = type of any & [idx:int64]\nlet Name = type of Token & [text:string]\nlet pick = (n:int64):>Token | int64 => if n >? 0 Name(idx=n text="x") else 0\nmain = () => match pick(1) { tk:Token => exit(tk.idx)  v:int64 => exit(2) }'))
