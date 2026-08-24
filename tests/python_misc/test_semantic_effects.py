from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.analyze.effects import (
    INDEX_STEP,
    ROOT,
    ParameterEffects,
    ProgramEffects,
    analyze_effects,
)


def _analyze(source: str) -> tuple[hir.Block, ProgramEffects]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return root, analyze_effects(root)


def _function(root: hir.Block, name: str) -> hir.FunctionLiteral:
    for item in root.items:
        if isinstance(item, hir.Declare) and item.name == name:
            expr = item.expr
            while (
                isinstance(expr, hir.Block)
                and not expr.scoped
                and len(expr.items) == 1
            ):
                expr = expr.items[0]
            assert isinstance(expr, hir.FunctionLiteral), name
            return expr
    raise AssertionError(f'no function declaration named {name}')


def _param_effects(
    effects: ProgramEffects,
    literal: hir.FunctionLiteral,
    index: int = 0,
) -> ParameterEffects:
    function_effects = effects.for_literal(literal)
    assert function_effects is not None
    parameter = literal.pos_or_kw_args[index]
    parameter_effects = function_effects.for_param(parameter)
    assert parameter_effects is not None
    return parameter_effects


def test_read_only_array_parameter() -> None:
    root, effects = _analyze('''
let sum = (items:array<int64 length=2>):>int64 => items[0] + items[1]
let main = ():>int64 => sum([1 2])
''')
    summary = _param_effects(effects, _function(root, 'sum'))
    assert summary.read_only
    assert not summary.writes
    assert summary.reads == {(INDEX_STEP,)}


def test_length_read_is_a_read() -> None:
    root, effects = _analyze('''
let measure = (items:array<int64 length=2>):>int64 => items.length
''')
    summary = _param_effects(effects, _function(root, 'measure'))
    assert summary.read_only
    assert summary.reads == {ROOT}


def test_index_write_records_element_mutation() -> None:
    root, effects = _analyze('''
let poke = (@items:array<int64 length=2>):>void => { items[0] = 40 }
let main = ():>void => {
    let values = [1 2]
    poke(@values)
}
''')
    summary = _param_effects(effects, _function(root, 'poke'))
    assert summary.mutates == {(INDEX_STEP,)}
    assert not summary.rebinds
    assert summary.writes
    assert not summary.read_only


def test_whole_value_rebinding() -> None:
    root, effects = _analyze('''
let reset = (@items:array<int64 length=2>):>void => { items = [7 8] }
let main = ():>void => {
    let values = [1 2]
    reset(@values)
}
''')
    summary = _param_effects(effects, _function(root, 'reset'))
    assert summary.rebinds == {ROOT}
    assert not summary.mutates


def test_object_field_mutation_records_field_route() -> None:
    root, effects = _analyze('''
let bump = (@box:[count:int64]):>void => { box.count = box.count + 1 }
let main = ():>void => {
    let cell = [count = 0]
    bump(@cell)
}
''')
    summary = _param_effects(effects, _function(root, 'bump'))
    assert summary.mutates == {('count',)}


def test_place_forwarding_propagates_mutation() -> None:
    root, effects = _analyze('''
let inner = (@items:array<int64 length=2>):>void => { items[1] = 5 }
let outer = (@items:array<int64 length=2>):>void => inner(@items)
let main = ():>void => {
    let values = [1 2]
    outer(@values)
}
''')
    summary = _param_effects(effects, _function(root, 'outer'))
    assert summary.mutates == {(INDEX_STEP,)}


def test_value_argument_to_writer_is_only_a_read() -> None:
    root, effects = _analyze('''
let scribble = (items:array<int64 length=2>):>int64 => {
    items[0] = 9
    return items[0]
}
let caller = (items:array<int64 length=2>):>int64 => scribble(items)
''')
    scribble = _param_effects(effects, _function(root, 'scribble'))
    assert scribble.mutates == {(INDEX_STEP,)}
    caller = _param_effects(effects, _function(root, 'caller'))
    assert caller.read_only
    assert caller.reads == {ROOT}


def test_indirect_call_keeps_value_argument_read_only() -> None:
    root, effects = _analyze('''
let apply = (f:<(x:array<int64 length=2>):>int64> items:array<int64 length=2>):>int64 => f(items)
''')
    apply = _function(root, 'apply')
    callable_summary = _param_effects(effects, apply, 0)
    items_summary = _param_effects(effects, apply, 1)
    assert callable_summary.reads == {ROOT}
    assert items_summary.read_only
    assert items_summary.reads == {ROOT}


def test_recursive_place_forwarding_reaches_fixed_point() -> None:
    root, effects = _analyze('''
let drain = (@items:array<int64 length=2> n:int64):>void => {
    if n >? 0 {
        items[0] = n
        drain(@items n - 1)
    }
}
let main = ():>void => {
    let values = [1 2]
    drain(@values 2)
}
''')
    summary = _param_effects(effects, _function(root, 'drain'))
    assert summary.mutates == {(INDEX_STEP,)}


def test_place_projection_translates_routes() -> None:
    root, effects = _analyze('''
let poke = (@cell:int64):>void => { cell = 7 }
let outer = (@box:[value:int64]):>void => poke(@box.value)
let main = ():>void => {
    let store = [value = 1]
    outer(@store)
}
''')
    poke = _param_effects(effects, _function(root, 'poke'))
    assert poke.rebinds == {ROOT}
    outer = _param_effects(effects, _function(root, 'outer'))
    assert outer.rebinds == {('value',)}
    assert not outer.mutates


def test_method_access_on_parameter_is_conservative() -> None:
    # A function-valued member captures its receiver, so touching it may
    # mutate sibling fields; the parameter must not look read-only.
    root, effects = _analyze('''
let call_method = (o:[a:int64 bump:<():>void>]):>int64 => {
    o.bump
    return o.a
}
''')
    summary = _param_effects(effects, _function(root, 'call_method'))
    assert not summary.read_only
    assert summary.mutates


def test_read_prefix_dominates_deeper_routes() -> None:
    root, effects = _analyze('''
let mixed = (items:array<int64 length=2>):>int64 => {
    let whole = items
    return items[0] + whole[1]
}
''')
    summary = _param_effects(effects, _function(root, 'mixed'))
    assert summary.reads == {ROOT}
    assert summary.read_only
