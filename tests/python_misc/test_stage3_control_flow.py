from typing import cast

import pytest

from src.cleanparse.backend.udewy import codegen
from src.cleanparse.parser import p0, t1
from src.cleanparse.reporting import SrcFile
from src.cleanparse.semantic import check, hir, ty
from src.cleanparse.semantic.errors import NotImplementedYet, TypeCheckError, UserError
from src.cleanparse.semantic.hir_display import hir_to_dewy, hir_to_tree_str


def _check(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return root


def _main_body(source: str) -> hir.Block:
    root = _check(source)
    main = next(
        item
        for item in root.items
        if isinstance(item, hir.Declare) and item.name == 'main'
    )
    assert isinstance(main.expr, hir.FunctionLiteral)
    assert isinstance(main.expr.body, hir.Block)
    return main.expr.body


def test_flow_conditions_require_bool() -> None:
    source = 'let main = ():>int64 => { if 1 { return 42 } return 0 }'

    with pytest.raises(TypeCheckError, match='type mismatch'):
        _check(source)


def test_exhaustive_conditional_uses_expected_scalar_type() -> None:
    body = _main_body(
        'let main = ():>int64 => { let x:int64 = if true 42 else 0 return x }'
    )
    declaration = body.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.Flow)
    assert declaration.expr.type == 'int64'


def test_non_exhaustive_statement_conditional_is_void() -> None:
    body = _main_body(
        'let main = ():>int64 => { if true { let x:int64 = 1 } return 42 }'
    )
    flow = body.items[0]
    assert isinstance(flow, hir.Flow)
    assert flow.type == ty.VOID_TYPE

    with pytest.raises(TypeCheckError, match='initializer expresses no value'):
        _check(
            'let main = ():>int64 => { let x = if true 42 return 0 }'
        )


def test_conditional_rejects_mixed_void_and_value_branches() -> None:
    source = """
let main = ():>int64 => {
    let x = if true { let y:int64 = 1 } else 2
    return 42
}
"""
    with pytest.raises(UserError, match='branches disagree'):
        _check(source)


def test_conditional_rejects_multi_value_results() -> None:
    source = 'let main = ():>int64 => { let x = if true (1 2) else (3 4) return 42 }'

    with pytest.raises(NotImplementedYet, match='multi-value conditional result'):
        _check(source)


@pytest.mark.parametrize('keyword', ['break', 'continue'])
def test_loop_exits_require_an_enclosing_loop(keyword: str) -> None:
    source = f'let main = ():>int64 => {{ {keyword} }}'

    with pytest.raises(UserError, match=f'`{keyword}` outside a loop'):
        _check(source)


@pytest.mark.parametrize(
    ('source', 'message'),
    [
        (
            'let main = ():>int64 => { do { return 42 } loop false { return 0 } }',
            '`do` flow',
        ),
        (
            'let main = ():>int64 => { match true { return 42 } }',
            '`match` flow',
        ),
        (
            'let main = ():>int64 => { if true { return 42 } else loop true { break } }',
            'mixed or advanced flow chain',
        ),
    ],
)
def test_deferred_flow_forms_have_focused_diagnostics(
    source: str,
    message: str,
) -> None:
    with pytest.raises(NotImplementedYet, match=message):
        _check(source)


def test_return_coverage_descends_through_exhaustive_flow() -> None:
    _check(
        'let main = ():>int64 => { if true { return 42 } else { return 0 } }'
    )

    with pytest.raises(UserError, match='not all paths return a value'):
        _check('let main = ():>int64 => { if true { return 42 } }')


def test_boolean_operator_syntax_is_lazy_but_other_dispatch_is_eager() -> None:
    body = _main_body("""
let diverge = ():>never => diverge()
let main = ():>int64 => {
    let word:bool = true and false
    let symbol:bool = true & false
    let negated:bool = true nand false
    let bottom:bool = false and diverge()
    let bits:int64 = 1 & 2
    let bits2:int64 = 1 nor 2
    let direct:bool = __and__(true false)
    return 42
}
""")
    declarations = {
        item.name: item.expr
        for item in body.items
        if isinstance(item, hir.Declare)
    }

    assert isinstance(declarations['word'], hir.ShortCircuit)
    assert isinstance(declarations['symbol'], hir.ShortCircuit)
    assert declarations['word'].op == declarations['symbol'].op == 'and'
    assert isinstance(declarations['negated'], hir.ShortCircuit)
    assert declarations['negated'].op == 'nand'
    assert isinstance(declarations['bottom'], hir.ShortCircuit)
    assert declarations['bottom'].right.type == ty.BOTTOM_TYPE
    assert isinstance(declarations['bits'], hir.FunctionCall)
    assert isinstance(declarations['bits2'], hir.FunctionCall)
    assert isinstance(declarations['direct'], hir.FunctionCall)

    emitted = codegen(SrcFile(None, """
let left = ():>bool => true
let right = ():>bool => false
let main = ():>int64 => {
    let direct:bool = __and__(left() right())
    return 42
}
"""))
    assert 'let __dewy_eager_1:bool = left()' in emitted
    assert 'let __dewy_eager_2:bool = right()' in emitted
    assert 'let direct:bool = __dewy_eager_1 and __dewy_eager_2' in emitted


def test_flow_display_covers_structured_nodes() -> None:
    body = _main_body("""
let main = ():>int64 => {
    loop true {
        if false and true {
            continue
        } else {
            break
        }
    }
    return 42
}
""")
    tree = hir_to_tree_str(body)
    rendered = hir_to_dewy(body)

    assert 'Flow(1 arms)' in tree
    assert 'LoopArm' in tree
    assert 'IfArm' in tree
    assert 'ShortCircuit(and)' in tree
    assert 'Continue' in tree
    assert 'Break' in tree
    assert 'loop true' in rendered
    assert 'if false and true' in rendered


def test_conditional_values_lower_to_typed_temporaries() -> None:
    emitted = codegen(SrcFile(
        None,
        'let main = ():>int64 => { return (if true 40 else 0) + 2 }',
    ))

    assert 'let __dewy_flow_1:int64 = 0' in emitted
    assert '__dewy_flow_1 = 40' in emitted
    assert 'return (__dewy_flow_1) + 2' in emitted


def test_parser_keeps_metatags_generic_while_hir_extracts_labels() -> None:
    parsed = p0.parse(SrcFile(None, '$outer\nbreak $outer'))
    assert isinstance(parsed.inner[0], p0.Atom)
    assert isinstance(parsed.inner[0].item, t1.Metatag)
    assert isinstance(parsed.inner[1], p0.KeywordExpr)
    parts = cast(list[object], parsed.inner[1].parts)
    assert isinstance(parts[1], list)
    assert len(parts[1]) == 1
    assert isinstance(parts[1][0], t1.Metatag)

    body = _main_body("""
let main = ():>void => {
    $outer
    loop true { break $outer }
}
""")
    assert isinstance(body.items[0], hir.ScopeMetatag)
    assert body.items[0].name == 'outer'
    flow = body.items[1]
    assert isinstance(flow, hir.Flow)
    loop = flow.arms[0]
    assert isinstance(loop, hir.LoopArm)
    assert isinstance(loop.body, hir.Block)
    exit_node = loop.body.items[0]
    assert isinstance(exit_node, hir.Break)
    assert exit_node.label == 'outer'
    assert exit_node.loop_levels == 0


def test_scope_metatag_visibility_is_scope_wide_and_allows_sibling_reuse() -> None:
    body = _main_body("""
let main = ():>void => {
    loop true { break $later }
    loop true { break $later }
    $later
    { $reused }
    { $reused }
}
""")
    for flow in body.items[:2]:
        assert isinstance(flow, hir.Flow)
        loop = flow.arms[0]
        assert isinstance(loop, hir.LoopArm)
        assert isinstance(loop.body, hir.Block)
        exit_node = loop.body.items[0]
        assert isinstance(exit_node, hir.Break)
        assert exit_node.label == 'later'
        assert exit_node.loop_levels == 0


@pytest.mark.parametrize(
    ('source', 'message'),
    [
        (
            'let main = ():>void => { $same $same }',
            r'duplicate scope metatag `\$same`',
        ),
        (
            'let main = ():>void => { { $same } $same }',
            r'scope metatag `\$same` shadows an active declaration',
        ),
        (
            'let main = ():>void => { loop true { break $missing } }',
            r'unknown loop label `\$missing`',
        ),
        (
            'let main = ():>void => { loop true { $inside break $inside } }',
            r'`\$inside` does not label an enclosing loop',
        ),
    ],
)
def test_scope_metatag_diagnostics(source: str, message: str) -> None:
    with pytest.raises(UserError, match=message):
        _check(source)


def test_scope_metatag_does_not_cross_a_nested_function_boundary() -> None:
    source = """
let main = ():>void => {
    $outer
    loop true {
        let local = ():>void => {
            loop true { break $outer }
        }
        break
    }
}
"""
    with pytest.raises(
        UserError,
        match=r'loop label `\$outer` cannot cross a function boundary',
    ):
        _check(source)


def test_labeled_exits_resolve_nearest_matching_loop_and_outward_distance() -> None:
    body = _main_body("""
let main = ():>void => {
    $outer
    loop true {
        $inner
        loop true {
            break $inner
        }
        loop true {
            loop true {
                if true {
                    break $outer
                } else {
                    continue $outer
                }
            }
        }
    }
}
""")

    exits: list[hir.Break | hir.Continue] = []

    def collect(node: hir.AST) -> None:
        if isinstance(node, (hir.Break, hir.Continue)):
            exits.append(node)
        elif isinstance(node, hir.Block):
            for item in node.items:
                collect(item)
        elif isinstance(node, hir.Flow):
            for arm in node.arms:
                collect(arm.body)
            if node.default is not None:
                collect(node.default)

    collect(body)
    assert [
        (type(exit_node), exit_node.label, exit_node.loop_levels)
        for exit_node in exits
    ] == [
        (hir.Break, 'inner', 0),
        (hir.Break, 'outer', 2),
        (hir.Continue, 'outer', 2),
    ]


def test_labeled_exit_display_and_signal_lowering() -> None:
    source = """
let main = ():>void => {
    $outer
    loop true {
        loop true {
            loop true {
                if true { break $outer } else { continue $outer }
            }
        }
    }
}
"""
    body = _main_body(source)
    tree = hir_to_tree_str(body)
    rendered = hir_to_dewy(body)
    emitted = codegen(SrcFile(None, source))

    assert 'ScopeMetatag($outer)' in tree
    assert 'Break($outer, loop_levels=2)' in tree
    assert 'Continue($outer, loop_levels=2)' in tree
    assert '$outer' in rendered
    assert 'break $outer' in rendered
    assert 'continue $outer' in rendered
    assert 'let __dewy_loop_levels_1:int64 = 0' in emitted
    assert 'let __dewy_loop_kind_1:int64 = 0' in emitted
    assert '__dewy_loop_levels_1 = 2' in emitted
    assert '__dewy_loop_levels_1 -= 1' in emitted
    assert '$outer' not in emitted


def test_labeled_exit_signals_do_not_shadow_source_bindings() -> None:
    emitted = codegen(SrcFile(None, """
let main = ():>void => {
    let __dewy_loop_levels_1:int64 = 0
    $outer
    loop true {
        loop true { break $outer }
    }
}
"""))

    assert 'let __dewy_loop_levels_1:int64 = 0' in emitted
    assert 'let __dewy_loop_levels_2:int64 = 0' in emitted
    assert 'let __dewy_loop_kind_2:int64 = 0' in emitted


def test_scope_metatags_are_elided_from_udewy_output() -> None:
    emitted = codegen(SrcFile(None, '$setting'))

    assert '$setting' not in emitted
    assert 'let main = ():>void' in emitted


def test_range_iterator_continue_advances_once_before_the_body() -> None:
    emitted = codegen(SrcFile(None, """
let main = ():>int64 => {
    let result:int64 = 0
    loop i in 0..2 {
        if i =? 1 { continue }
        result += i
    }
    return result
}
"""))

    increment = emitted.index('__dewy_iterator_1 += 1')
    source_continue = emitted.index('continue', increment)
    assert increment < source_continue
    assert emitted.count('__dewy_iterator_1 += 1') == 1


def test_labeled_exits_preserve_depth_through_range_iterators() -> None:
    source = """
let main = ():>void => {
    $outer
    loop i in 0..2 {
        loop true {
            if i =? 1 { continue $outer }
            break $outer
        }
    }
}
"""
    body = _main_body(source)
    outer = body.items[1]
    assert isinstance(outer, hir.Flow)
    inner = cast(hir.Block, outer.arms[0].body).items[0]
    assert isinstance(inner, hir.Flow)
    conditional = cast(hir.Block, inner.arms[0].body).items[0]
    assert isinstance(conditional, hir.Flow)
    continued = cast(hir.Block, conditional.arms[0].body).items[0]
    assert isinstance(continued, hir.Continue)
    assert continued.loop_levels == 1

    emitted = codegen(SrcFile(None, source))
    assert '__dewy_loop_levels_1 = 1' in emitted
    assert '$outer' not in emitted
