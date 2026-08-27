import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, UserError


def _codegen(source: str) -> str:
    return codegen(SrcFile(None, source))


def _check(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return root


def test_direct_function_use_before_declaration_is_rejected() -> None:
    source = """
later()
let later = ():>int64 => 42
"""
    with pytest.raises(UserError, match='`later` used before initialization'):
        _check(source)


def test_transitive_function_use_before_declaration_is_rejected() -> None:
    source = """
let first = ():>int64 => later()
first()
let later = ():>int64 => 42
"""
    with pytest.raises(UserError, match='`later` used before initialization'):
        _check(source)


def test_statically_unreachable_branch_does_not_require_initialization() -> None:
    source = """
let first = ():>int64 => if false later() else 42
first()
let later = ():>int64 => 0
"""
    _check(source)


def test_potential_branch_use_requires_initialization() -> None:
    source = """
let condition:bool = true
let first = ():>int64 => if condition later() else 42
first()
let later = ():>int64 => 0
"""
    with pytest.raises(UserError, match='`later` used before initialization'):
        _check(source)


def test_unknown_callback_use_is_checked_conservatively() -> None:
    source = """
let invoke = (fn:<():>int64>):>int64 => fn()
let first = ():>int64 => later()
invoke(@first)
let later = ():>int64 => 42
"""
    with pytest.raises(UserError, match='`later` used before initialization'):
        _check(source)


def test_actual_callback_effect_does_not_include_unrelated_functions() -> None:
    source = """
let invoke = (fn:<():>int64>):>int64 => fn()
let ready = ():>int64 => 42
invoke(@ready)
let unrelated = ():>int64 => 0
"""
    _check(source)


def test_callback_effects_propagate_through_function_parameters() -> None:
    source = """
let invoke = (fn:<():>int64>):>int64 => fn()
let relay = (fn:<():>int64>):>int64 => invoke(@fn)
let ready = ():>int64 => 42
relay(@ready)
let unrelated = ():>int64 => 0
"""
    _check(source)


def test_callable_alternatives_union_their_initialization_effects() -> None:
    source = """
let condition:bool = true
let ready = ():>int64 => 42
let first = ():>int64 => later()
let callback:<():>int64> = if condition @ready else @first
callback()
let later = ():>int64 => 0
"""
    with pytest.raises(UserError, match='`later` used before initialization'):
        _check(source)


def test_forward_reference_is_valid_when_called_after_declaration() -> None:
    source = """
let first = ():>int64 => later()
let later = ():>int64 => 42
let main = ():>int64 => first()
"""
    _check(source)
    assert 'return first()' in _codegen(source)


def test_self_and_mutual_recursion_are_valid_after_initialization() -> None:
    source = """
let countdown = (value:int64):>int64 => {
    if value =? 0 { return 20 }
    return countdown(value - 1)
}
let even = (value:int64):>int64 => {
    if value =? 0 { return 22 }
    return odd(value - 1)
}
let odd = (value:int64):>int64 => {
    if value =? 0 { return 0 }
    return even(value - 1)
}
let main = ():>int64 => countdown(2) + even(2)
"""
    _check(source)
    emitted = _codegen(source)
    assert 'return countdown(value - 1)' in emitted
    assert 'return odd(value - 1)' in emitted


def test_local_function_use_before_declaration_is_rejected() -> None:
    source = """
let main = ():>int64 => {
    let ignored:int64 = first()
    let first = ():>int64 => 42
    return ignored
}
"""
    with pytest.raises(UserError, match='`first` used before initialization'):
        _check(source)


def test_function_defaults_are_initialized_at_the_declaration_site() -> None:
    source = """
let invoke = (... fn:<():>int64>=@later):>int64 => fn()
let later = ():>int64 => 42
"""
    with pytest.raises(UserError, match='`later` used before initialization'):
        _check(source)


def test_positional_default_callback_uses_its_call_site_effects() -> None:
    source = """
let callback = ():>int64 => later()
let invoke = (fn:<():>int64>=@callback):>int64 => fn()
invoke()
let later = ():>int64 => 42
"""
    with pytest.raises(UserError, match='`later` used before initialization'):
        _check(source)


def test_deferred_function_body_can_read_a_later_initialized_value() -> None:
    source = """
let read = ():>int64 => value
let value:int64 = 42
let main = ():>int64 => read()
"""
    _check(source)


def test_call_before_a_deferred_value_is_initialized_is_rejected() -> None:
    source = """
let read = ():>int64 => value
read()
let value:int64 = 42
"""
    with pytest.raises(UserError, match='`value` used before initialization'):
        _check(source)


def test_eager_value_expression_cannot_resolve_a_later_value() -> None:
    source = """
let result:int64 = value
let value:int64 = 42
"""
    with pytest.raises(UserError, match='undefined identifier `value`'):
        _check(source)


def test_local_deferred_value_access_uses_call_site_state() -> None:
    valid = """
let main = ():>int64 => {
    let read = ():>int64 => value
    let value:int64 = 42
    return read()
}
"""
    _check(valid)

    invalid = """
let main = ():>int64 => {
    let read = ():>int64 => value
    let result:int64 = read()
    let value:int64 = 42
    return result
}
"""
    with pytest.raises(UserError, match='`value` used before initialization'):
        _check(invalid)


def test_reassigned_callable_effect_is_reported_as_unresolved() -> None:
    source = """
let ready = ():>int64 => 42
let first = ():>int64 => later()
let callback:<():>int64> = @ready
callback = @first
callback()
let later = ():>int64 => 0
"""
    with pytest.raises(
        NotImplementedYet,
        match='callable initialization effect is not resolved',
    ):
        _check(source)


def test_main_must_take_no_arguments() -> None:
    source = 'let main = (value:int64):>int64 => value'
    with pytest.raises(UserError, match='`main` must take no arguments'):
        _check(source)


def test_main_must_return_an_exit_code_or_void() -> None:
    source = 'let main = ():>bool => true'
    with pytest.raises(UserError, match='`main` must return an integer or `void`'):
        _check(source)


def test_main_may_infer_its_integer_return_type() -> None:
    root = _check('let main = () => 42')
    declaration = root.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.FunctionLiteral)
    assert isinstance(declaration.expr.rettype, ty.IntegerLiteralType)
    assert declaration.expr.rettype.value == 42
    assert 'let main = ():>int64' in _codegen('let main = () => 42')


def test_checked_hir_records_binding_identity() -> None:
    root = _check("""
let value:int64 = 42
let main = ():>int64 => value
""")
    value = root.items[0]
    main = root.items[1]
    assert isinstance(value, hir.Declare)
    assert isinstance(main, hir.Declare)
    assert isinstance(main.expr, hir.FunctionLiteral)
    assert isinstance(main.expr.body, hir.ExpressedIdentifier)
    assert value.binding_id is not None
    assert main.expr.body.binding_id == value.binding_id


def test_function_only_program_without_main_gets_empty_entrypoint() -> None:
    emitted = _codegen('let helper = ():>int64 => 42')
    assert 'let helper = ():>int64' in emitted
    assert 'let main = ():>void' in emitted


def test_inferred_integer_globals_and_main_use_abstract_int_storage() -> None:
    emitted = _codegen("""
let value = 42
let main = () => value
""")

    assert 'let value:int = 0' in emitted
    assert 'let __dewy_user_main = ():>int' in emitted
    assert 'let main = ():>int' in emitted


def test_void_main_wrapper_runs_startup_then_returns_void() -> None:
    emitted = _codegen("""
let value:int64 = 0
let main = ():>void => {
    value = 1
}
""")

    wrapper = emitted.index('let main = ():>void')
    assert emitted.index('__dewy_top_level()', wrapper) < emitted.index(
        '__dewy_user_main()',
        wrapper,
    )
    assert 'return void' in emitted[wrapper:]


def test_top_level_const_uses_private_mutable_startup_storage() -> None:
    emitted = _codegen("""
const value:int64 = 42
let main = ():>int64 => value
""")

    assert 'let value:int64 = 0' in emitted
    assert 'value = 42' in emitted


def test_global_string_storage_is_initialized_during_startup() -> None:
    source = """
let message = "hello"
let main = ():>int64 => 0
"""
    emitted = _codegen(source)
    assert 'let message:int64 = 0' in emitted
    assert 'message = __dewy_string_value_' in emitted


def test_generated_startup_symbol_avoids_source_bindings() -> None:
    source = """
let __dewy_top_level:int64 = 42
let main = ():>int64 => __dewy_top_level
"""
    emitted = _codegen(source)
    assert 'let __dewy_top_level:int64 = 0' in emitted
    assert 'let __dewy_top_level_2 = ():>void' in emitted
    assert '__dewy_top_level_2()' in emitted


def test_main_may_take_argv_strings_only() -> None:
    from dewy.reporting import SrcFile
    from dewy.semantic import check
    check.typecheck_and_resolve(SrcFile(None, 'let main = (args:array<string>):>int64 => args.length'))
    with pytest.raises(UserError, match='array<string>'):
        check.typecheck_and_resolve(SrcFile(None, 'let main = (n:int64):>int64 => n'))
