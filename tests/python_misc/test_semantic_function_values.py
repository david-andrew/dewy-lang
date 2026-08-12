import pytest

from src.cleanparse.backend.udewy import codegen
from src.cleanparse.reporting import SrcFile
from src.cleanparse.semantic import check, hir, ty
from src.cleanparse.semantic.errors import NotImplementedYet
from src.cleanparse.semantic.hir_display import type_to_dewy


def _function_type(name: str | None = None) -> ty.FunctionType:
    return ty.FunctionType(
        [ty.PosOrKwArg(name, 'int64')],
        [],
        None,
        'int64',
    )


def test_named_and_unnamed_function_type_contracts() -> None:
    type_system = ty.TypeSystem()
    unnamed = _function_type()
    named_x = _function_type('x')
    named_y = _function_type('y')

    assert type_system.function_subtype(named_x, unnamed)
    assert not type_system.function_subtype(unnamed, named_x)
    assert not type_system.function_subtype(named_y, named_x)
    assert type_system.call_accepted(unnamed, ['int64'], {})
    assert not type_system.call_accepted(unnamed, [], {'x': 'int64'})


def test_structural_function_type_display() -> None:
    assert type_to_dewy(_function_type()) == '<int64:>int64>'
    assert type_to_dewy(_function_type('x')) == '<(x:int64):>int64>'
    assert type_to_dewy(
        ty.FunctionType(
            [ty.PosOrKwArg(None, 'int64'), ty.PosOrKwArg(None, 'bool')],
            [],
            None,
            'int64',
        )
    ) == '<(int64 bool):>int64>'


def test_callable_values_and_pipe_share_function_call_hir() -> None:
    source = """
let double = (x:int64):>int64 => {
    return x * 2
}
let choose = ():><int64:>int64> => {
    return double
}
let apply = (fn:<int64:>int64> value:int64):>int64 => {
    return fn(value)
}
let main = ():>int64 => {
    let fn_ptr:<int64:>int64> = choose()
    let indirect:int64 = (fn_ptr)(5)
    let piped:int64 = 6 |> fn_ptr
    return apply(fn_ptr indirect + piped)
}
"""
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    choose = root.items[1]
    main = root.items[-1]
    assert isinstance(choose, hir.Declare)
    assert isinstance(choose.expr, hir.FunctionLiteral)
    assert choose.expr.rettype == _function_type()
    assert isinstance(main, hir.Declare)
    assert isinstance(main.expr, hir.FunctionLiteral)
    assert isinstance(main.expr.body, hir.Block)

    locals_by_name = {
        item.name: item
        for item in main.expr.body.items
        if isinstance(item, hir.Declare)
    }
    for name in ('indirect', 'piped'):
        call = locals_by_name[name].expr
        assert isinstance(call, hir.FunctionCall)
        assert isinstance(call.func, hir.ExpressedIdentifier)
        assert call.func.name == 'fn_ptr'


def test_udewy_backend_hoists_non_capturing_local_functions() -> None:
    source = """
let main = ():>int64 => {
    let local = (value:int64):>int64 => value
    return local(42)
}
"""
    emitted = codegen(SrcFile(None, source))
    assert 'let local = (value:int64):>int64' in emitted
    assert 'return local(42)' in emitted


def test_udewy_backend_rejects_captured_local_values() -> None:
    source = """
let outer = (value:int64):>int64 => {
    let local = ():>int64 => value
    return local()
}
let main = ():>int64 => outer(42)
"""
    with pytest.raises(NotImplementedYet, match='captures `value`'):
        codegen(SrcFile(None, source))
