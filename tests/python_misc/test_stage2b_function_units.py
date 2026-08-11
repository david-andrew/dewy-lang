import pytest

from src.cleanparse.backend.udewy import codegen
from src.cleanparse.reporting import SrcFile
from src.cleanparse.semantic import check, hir
from src.cleanparse.semantic.errors import NotImplementedYet


def _declarations(block: hir.Block) -> dict[str, hir.Declare]:
    return {
        item.name: item
        for item in block.items
        if isinstance(item, hir.Declare)
    }


def test_overload_calls_record_flat_method_indices() -> None:
    source = """
let zero = ():>int64 => 20
let identity = (x:int64):>int64 => x
let sum = (left:int64 right:int64):>int64 => left + right
let choose = zero & identity
let nested = choose & sum
let main = ():>int64 => {
    let a:int64 = nested()
    let b:int64 = nested(2)
    let c:int64 = nested(10 10)
    return a + b + c
}
"""
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    main = _declarations(root)['main']
    assert isinstance(main.expr, hir.FunctionLiteral)
    assert isinstance(main.expr.body, hir.Block)
    locals_by_name = _declarations(main.expr.body)

    assert isinstance(locals_by_name['a'].expr, hir.FunctionCall)
    assert locals_by_name['a'].expr.selected_method_index == 0
    assert isinstance(locals_by_name['b'].expr, hir.FunctionCall)
    assert locals_by_name['b'].expr.selected_method_index == 1
    assert isinstance(locals_by_name['c'].expr, hir.FunctionCall)
    assert locals_by_name['c'].expr.selected_method_index == 2


def test_nested_overloads_lower_to_existing_concrete_symbols() -> None:
    source = """
let zero = ():>int64 => 20
let identity = (x:int64):>int64 => x
let sum = (left:int64 right:int64):>int64 => left + right
let choose = zero & identity
let nested = choose & sum
let main = ():>int64 => {
    return nested() + nested(2) + nested(10 10)
}
"""
    emitted = codegen(SrcFile(None, source))

    assert 'let choose =' not in emitted
    assert 'let nested =' not in emitted
    assert 'return (zero() + identity(2)) + sum(10 10)' in emitted


def test_inline_overloads_use_readable_signatures_and_ordinals() -> None:
    source = """
let choose = ((x:int64):>int64 => x) & ((x:int64):>int64 => x + 1)
let main = ():>int64 => 42
"""
    emitted = codegen(SrcFile(None, source))

    assert 'let choose__x_int64_to_int64 =' in emitted
    assert 'let choose__x_int64_to_int64__overload_2 =' in emitted
    assert '__hash' not in emitted


def test_same_local_name_in_distinct_scopes_is_qualified() -> None:
    source = """
let main = ():>int64 => {
    let left:int64 = {
        let helper = ():>int64 => 20
        helper()
    }
    let right:int64 = {
        let helper = ():>int64 => 22
        helper()
    }
    return left + right
}
"""
    emitted = codegen(SrcFile(None, source))

    assert 'let helper__in_main__scope_1 =' in emitted
    assert 'let helper__in_main__scope_2 =' in emitted
    assert 'helper__in_main__scope_1()' in emitted
    assert 'helper__in_main__scope_2()' in emitted


def test_runtime_multifunction_values_are_rejected() -> None:
    source = """
let zero = ():>int64 => 20
let identity = (x:int64):>int64 => x
let choose = zero & identity
let get = () => choose
let main = ():>int64 => 42
"""
    with pytest.raises(NotImplementedYet, match='runtime multifunction values'):
        codegen(SrcFile(None, source))
