"""Checker-level coverage for the 2026-09-01 bootstrap-gap fixes and diagnostics."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import TypeCheckError, UserError


def _check(source: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, source))


def test_double_equals_names_the_real_operator() -> None:
    with pytest.raises(UserError, match='`==` is not an operator') as info:
        _check('let main = ():>int64 => {\n    let x = 1\n    if x == 1 { return 1 }\n    return 0\n}')
    assert 'equality is `=?`' in str(info.value.report)


def test_colon_result_type_hints_the_arrow() -> None:
    with pytest.raises(UserError, match='result type is written `:>`'):
        _check('main = (argv:array<string>):int64 => {\n    return 0\n}')


def test_optional_returning_main_is_an_error_not_a_crash() -> None:
    with pytest.raises(UserError, match='`main` must return an integer or `void`'):
        _check('let main = (argv:array<string>):>uint64? => {\n    return none\n}')


def test_unproven_index_blames_the_unknown_length() -> None:
    with pytest.raises(UserError, match='array index is not proven') as info:
        _check('let main = (argv:array<string>):>int64 => {\n    printl(argv[0])\n    return 0\n}')
    report = str(info.value.report)
    assert 'nothing establishes the array' in report and 'guard on the length first' in report


def test_mixed_width_comparison_casts_the_right_operand_with_a_proof() -> None:
    _check('let f = (i:uint64 s:string):>bool => i <? s.length')
    with pytest.raises(UserError, match='cannot prove this integer fits `uint8`'):
        _check('let f = (i:uint8 w:int64):>bool => i <? w')   # the proof still gates it


def test_nested_unpacking_takes_fields_by_name() -> None:
    _check("let d:dict<string [a:int64 b:int64]> = ['x' -> [a=1 b=2]]\nlet main = ():>int64 => {\n    let t:int64 = 0\n    loop [k [b a]] in d { t += a + b }\n    return t\n}")
    _check("let d:dict<string [a:int64 b:int64]> = ['x' -> [a=1 b=2]]\nlet main = ():>int64 => {\n    loop [k [a]] in d { }\n    return 0\n}")   # a subset
    with pytest.raises(UserError, match='no field `c` to unpack'):
        _check("let d:dict<string [a:int64 b:int64]> = ['x' -> [a=1 b=2]]\nlet main = ():>int64 => {\n    loop [k [c]] in d { }\n    return 0\n}")


def test_intersection_strengthens_but_never_weakens() -> None:
    root = _check("Context:type = [depth:int64]\nRoot = Context & [tag:string='root']\nlet r = Root(depth=1)")
    declare = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'r')
    assert [field.name for field in declare.expr.type.fields] == ['depth', 'tag']   # type: ignore[union-attr]
    with pytest.raises(TypeCheckError, match='weakens'):
        _check("A:type = [x:int8]\nB = A & [x:int64]\nlet b = B(x=1)")


def test_minted_override_keeps_the_subtype_rule() -> None:
    _check("let Report = type of any & [severity='none']\nlet Err = type of Report & [severity='error']")
    with pytest.raises(UserError, match='weakens field'):
        _check("let A = type of any & [x:int8]\nlet B = type of A & [x:int64]")


def test_foreign_spellings_get_a_hint() -> None:
    """Dewy is case-sensitive: `True`, `AND`, `Let` are undefined names, and the
    error says what to write; so do other languages' spellings (`None`,
    `elif`) and an uppercase base prefix (`0X1f`)."""
    import pytest
    from dewy.reporting import SrcFile
    from dewy.semantic import check
    from dewy.semantic.errors import UserError

    def hint_for(source: str) -> str:
        with pytest.raises(UserError) as caught:
            check.typecheck_and_resolve(SrcFile(None, source + '\nlet main = ():>int64 => 42\n'))
        return caught.value.report.hint or ''

    assert 'write `true`' in hint_for('let x = True')
    assert 'write `none`' in hint_for('let x = NONE')
    assert 'keyword is `and`' in hint_for('let x = 1 AND 2')
    assert 'keyword is `let`' in hint_for('Let x = 1')
    assert 'write `none`' in hint_for('let x = None')
    assert 'else if' in hint_for('let x = elif')
    assert '`0x1f`' in hint_for('let x = 0X1f')
    assert hint_for('let x = fooBar') == ''


def test_a_bare_return_ends_at_its_line() -> None:
    """`return`/`yield` take a value only from their own line: `if c return` then
    a statement on the next line returns nothing (the statement is not the
    value); a value on the same line may continue onto later lines; `;` still
    ends a bare return; `return` without a value at the end of a block stays bare."""
    from dewy.reporting import SrcFile
    from dewy.semantic import check, hir

    def declared(source: str):
        root = check.typecheck_and_resolve(SrcFile(None, source))
        return {item.name: item for item in root.items if isinstance(item, hir.Declare)}

    def returns(fn):
        found = []
        def walk(node):
            if isinstance(node, hir.Return):
                found.append(node)
            from dataclasses import fields, is_dataclass
            if is_dataclass(node):
                for f in fields(node):
                    v = getattr(node, f.name)
                    if isinstance(v, hir.AST): walk(v)
                    elif isinstance(v, (list, tuple)):
                        for i in v:
                            if isinstance(i, hir.AST): walk(i)
        walk(fn)
        return found

    source = (
        'let count = (@n:int64 result:int64?):>void => {\n'
        '    if result is? none return\n'
        '    n += result\n'
        '}\n'
        'let spread = (a:int64 b:int64):>int64 => {\n'
        '    return a +\n'
        '        b\n'
        '}\n'
        'let semi = (@n:int64):>void => { if n >? 0 return;  n += 1 }\n'
        'let main = ():>int64 => 42\n'
    )
    d = declared(source)
    count_returns = returns(d['count'].expr)
    assert len(count_returns) == 1 and count_returns[0].item is None      # bare: the next line is not its value
    spread_returns = returns(d['spread'].expr)
    assert len(spread_returns) == 1 and spread_returns[0].item is not None   # the value began on the keyword's line
    semi_returns = returns(d['semi'].expr)
    assert len(semi_returns) == 1 and semi_returns[0].item is None
