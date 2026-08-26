import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import UserError
from dewy.backend.udewy import codegen


def _check(source: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, '$no_prelude = true\n' + source))


def test_exhaustive_is_chain_needs_no_else_for_returns() -> None:
    root = _check(
        'let f = (v:int64|string):>int64 => {\n'
        '    if v is? int64 { return v } else if v is? string { return 0 }\n'
        '}'
    )
    f = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'f')
    flow = f.expr.body.items[0]
    assert isinstance(flow, hir.Flow)
    assert len(flow.arms) == 1 and flow.default is not None  # last arm became the default


def test_exhaustive_is_chain_produces_a_value() -> None:
    root = _check(
        'let f = (v:int64|bool):>int64 => {\n'
        '    let w:int64 = if v is? int64 v else if v is? bool 1\n'
        '    return w\n'
        '}'
    )
    assert root is not None


def test_missing_member_is_reported_for_value_chains() -> None:
    with pytest.raises(UserError, match='`undefined` is not handled by any `is\\?` arm'):
        _check(
            'let f = (v:int64|undefined):>int64 => {\n'
            '    let w:int64 = if v is? int64 v\n'
            '    return w\n'
            '}'
        )


def test_incomplete_return_chain_still_fails_coverage() -> None:
    with pytest.raises(UserError, match='not all paths return'):
        _check(
            'let f = (v:int64|string|undefined):>int64 => {\n'
            '    if v is? int64 { return v } else if v is? string { return 0 }\n'
            '}'
        )


def test_statement_chains_do_not_need_to_be_exhaustive() -> None:
    _check(
        'let f = (v:int64|string):>void => {\n'
        '    if v is? int64 { let x = v }\n'
        '}'
    )


def test_module_level_unions_get_static_cells() -> None:
    emitted = codegen(SrcFile(None, (
        '$no_prelude = true\n'
        'let state:int64|string = 5\n'
        'let boxed:[value:int64]|bool = [value = 9]\n'
        'let main = ():>int64 => {\n'
        '    state = "x"\n'
        '    if boxed is? [value:int64] { return boxed.value }\n'
        '    return 0\n'
        '}\n'
    )))
    startup = emitted.split('let __dewy_top_level', 1)[1]
    assert startup.count('__static_alloca__(') >= 2  # one cell per union global (plus member trees)
    assert 'let state:int64 = 0' in emitted and 'let boxed:int64 = 0' in emitted
