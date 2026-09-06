"""Operator sections: `(<? n)` is the function `i => i <? n` — the left-missing form
only, for operators with no prefix form — usable wherever a one-parameter function
is, including as a fact (`uint64<(<? src.length)>`, `uint64<(in? 1..3)>`)."""
import pytest

from dewy.parser import p0, t1, t2
from dewy.reporting import SrcFile
from dewy.semantic import check, ty
from dewy.semantic.errors import TypeCheckError, UserError
from dewy.semantic.hir_display import type_to_dewy


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source), include_prelude=True)


def _parsed(source: str) -> p0.AST:
    return p0.parse(SrcFile(None, source)).inner[0]


def _is_lambda(ast: p0.AST) -> bool:
    while isinstance(ast, p0.Block) and ast.kind == '()' and len(ast.inner) == 1:
        ast = ast.inner[0]
    return isinstance(ast, p0.BinOp) and isinstance(ast.op, t1.Operator) and ast.op.symbol == '=>' and isinstance(ast.left, p0.Atom) and ast.left.item.name == t2.SECTION_PARAMETER


def test_a_section_parses_as_a_hidden_parameter_lambda() -> None:
    for source in ['(<? 10)', '(=? 0)', '(in? 1..3)', '(is? Word)', '(not in? whitespace)', '(.length)', '(as string)', '(% 3)', '(^ 2)', '(<? a + b)']:
        assert _is_lambda(_parsed(source + '\n')), source
    # operators with a prefix form are not sections (`(- 1)` is negative one), nor is `(op)` alone or a plain group
    for source in ['(- 1)', '(+ 1)', '(not x)', '(~x)', '(<?)', '(x <? 10)']:
        assert not _is_lambda(_parsed(source + '\n')), source
    negative = _parsed('(- 1)\n')
    while isinstance(negative, p0.Block):
        negative = negative.inner[0]
    assert isinstance(negative, p0.Prefix)


def test_sections_are_function_values_typed_by_their_context() -> None:
    program = '''let main = ():>int64 => {
    let small:<(x:int64):>bool> = (<? 10)          # takes the slot's parameter name
    let xs:array<int64> = [3 12 7 20]
    let n:int64 = 0
    loop x in xs { if small(x) { n += 1 } }
    let names:array<string> = ["bb" "a" "ccc"]
    names.sort(key=(.length))                       # a direct call of the literal, like `(s) => s.length`
    return n
}
'''
    _check(program)
    with pytest.raises(TypeCheckError, match='expresses no value'):   # no context, like `let f = i => i <? 10`
        _check('let small = (<? 10)\n')


def test_sections_and_ranges_are_facts() -> None:
    program = '''let main = ():>int64 => {
    let text = "hello"
    let k:uint64<(<? text.length)> = 3
    let piece = text[0..k)
    let m:uint64<(in? 1..3)> = 2
    let e:uint64<(in? [1..3))> = 2
    let big:uint64<i => i in? 10..20> = 15
    return 0
}
'''
    _check(program)
    with pytest.raises(TypeCheckError, match='refinement refuted'):
        _check(program.replace('let m:uint64<(in? 1..3)> = 2', 'let m:uint64<(in? 1..3)> = 5'))
    with pytest.raises(TypeCheckError, match='refinement refuted'):
        _check(program.replace('let e:uint64<(in? [1..3))> = 2', 'let e:uint64<(in? [1..3))> = 3'))   # exclusive end
    root = check.typecheck_and_resolve(SrcFile(None, 'let f = (n:uint64<(in? 1..3)>):>uint64 => n\n'), include_prelude=True)
    declaration = next(item for item in root.items if getattr(item, 'name', None) == 'f')
    param = declaration.expr.pos_or_kw_args[0].type
    assert isinstance(param, ty.RefinedType) and {(p.op, p.value) for p in param.propositions} == {('>=?', 1), ('<=?', 3)}
