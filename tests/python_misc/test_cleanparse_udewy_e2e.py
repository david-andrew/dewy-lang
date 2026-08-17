from pathlib import Path
from shutil import which

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from udewy.frontend import entry_point

here = Path(__file__).parent
repo = here.parent.parent
fixtures = repo / 'dewy' / 'tests'


def x86_64_toolchain_available() -> bool:
    return which('as') is not None and which('ld') is not None


ROUNDTRIP_CASES = [
    ('minimal2.udewy', 42),
    ('arith_locals.udewy', 42),
    ('direct_calls.udewy', 42),
    ('assign_basic.udewy', 42),
    ('div_mod_scalar.udewy', 0),
    ('forward_calls.udewy', 42),
    ('recursive_symbol.udewy', 42),
]
LOWERED_CASES = [
    ('overload_calls.dewy', 42),
    ('inline_overloads.dewy', 42),
    ('local_functions.dewy', 42),
    ('if_else.dewy', 42),
    ('if_value.dewy', 42),
    ('if_else_if.dewy', 42),
    ('loop_count.dewy', 42),
    ('loop_break.dewy', 42),
    ('loop_continue.dewy', 42),
    ('labeled_loop_exits.dewy', 42),
    ('cond_short_circuit.dewy', 42),
    ('fib_if.dewy', 55),
    ('top_level_then_main.dewy', 42),
    ('top_level_control_flow.dewy', 42),
    ('top_level_without_main.dewy', 0),
    ('explicit_and_implicit_main.dewy', 2),
    ('top_level_inferred_global.dewy', 42),
    ('top_level_callback.dewy', 42),
    ('array_local_sum.dewy', 42),
    ('array_narrow.dewy', 42),
    ('array_module_lookup.dewy', 42),
    ('array_fresh_local.dewy', 42),
    ('array_while_index.dewy', 42),
    ('array_range_sum.dewy', 42),
    ('array_dynamic_narrow.dewy', 42),
    ('array_call_adapters.dewy', 42),
    ('range_bound_forms.dewy', 42),
    ('iterator_labeled_exits.dewy', 42),
    ('optional_values.dewy', 42),
    ('optional_layouts.dewy', 42),
    ('optional_calls.dewy', 42),
    ('multi_iterator_and.dewy', 42),
    ('multi_iterator_or.dewy', 42),
    ('multi_iterator_formula.dewy', 42),
    ('multi_iterator_exhausted_truth.dewy', 42),
    ('multi_iterator_labeled_exits.dewy', 42),
    ('multi_iterator_operators.dewy', 42),
    ('range_stepped.dewy', 42),
    ('range_stepped_array.dewy', 42),
    ('range_stepped_labeled_exits.dewy', 42),
    ('range_stepped_multi_optional.dewy', 42),
    ('object_fields.dewy', 42),
    ('object_nested.dewy', 42),
    ('object_methods.dewy', 42),
    ('object_types.dewy', 42),
    ('object_regressions.dewy', 42),
    ('unicode_strings.dewy', 42),
    ('string_ranges.dewy', 42),
    ('string_containers.dewy', 42),
    ('runtime_grapheme_strings.dewy', 42),
    ('jump_table.dewy', 42),
    ('keyword_default_calls.dewy', 42),
    ('path_values.dewy', 42),
    ('hello_world_syscall.dewy', 0),
]
CASES = [*ROUNDTRIP_CASES, *LOWERED_CASES]
ROUNDTRIP_FIXTURE_NAMES = [fixture_name for fixture_name, _ in ROUNDTRIP_CASES]


@pytest.mark.parametrize('fixture_name', ROUNDTRIP_FIXTURE_NAMES)
def test_udewy_fixture_roundtrip(fixture_name: str) -> None:
    path = fixtures / fixture_name
    source = path.read_text()
    no_prelude = SrcFile(path, f'$no_prelude = true\n{source}')
    assert codegen(no_prelude) == source


@pytest.mark.parametrize(('fixture_name', 'expected_exit'), CASES)
@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_udewy_fixture_compiles_and_runs(
    fixture_name: str,
    expected_exit: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted = codegen(SrcFile.from_path(fixtures / fixture_name))

    udewy_path = tmp_path / fixture_name
    udewy_path.write_text(emitted)

    # entry_point writes __dewycache__ relative to cwd; keep artifacts in tmp_path
    monkeypatch.chdir(tmp_path)
    exit_code = entry_point(udewy_path, [])
    assert exit_code == expected_exit


def test_fixed_local_array_fixtures_use_stack_data() -> None:
    local_sum = codegen(SrcFile.from_path(fixtures / 'array_local_sum.dewy'))
    assert 'let values:int64 = __alloca__(24)' in local_sum
    assert '__store_i64__(10 values)' in local_sum
    assert '__load_i64__(values + 16)' in local_sum
    assert '__alloca__(48)' not in local_sum

    dynamic = codegen(SrcFile.from_path(fixtures / 'array_dynamic_narrow.dewy'))
    assert 'let bytes:int64 = __alloca__(3)' in dynamic
    assert 'loop i <? 3' in dynamic
    assert '__store_u8__(42 bytes + 1)' in dynamic
    assert 'return __load_u8__(bytes + 1)' in dynamic
    assert '__load_i64__(bytes' not in dynamic
    assert '__alloca__(48)' not in dynamic

    recursive = codegen(SrcFile.from_path(fixtures / 'array_fresh_local.dewy'))
    assert 'let probe = (depth:int64):>int64 => {\n    let values:int64 = __alloca__(8)' in recursive
    assert '__store_i64__(40 values)' in recursive
    assert 'let ignored:int64 = probe(1)' in recursive
    assert 'return __load_i64__(values)' in recursive
    assert '__alloca__(48)' not in recursive


def test_array_call_adapter_fixture_codegen_shape() -> None:
    emitted = codegen(SrcFile.from_path(fixtures / 'array_call_adapters.dewy'))

    assert 'const words:int64 = __static_words__(0 2)' in emitted
    assert 'const bytes:int64 = 0x"2802"' in emitted
    assert 'let local:int64 = __alloca__(16)' in emitted
    assert 'let alias:int64 = local' in emitted
    assert 'let transitive:int64 = alias' in emitted
    assert emitted.count('__alloca__(48)') == 4
    assert '__store_i64__(transitive __dewy_array_1)' in emitted
    assert '__store_i64__(words __dewy_array_2)' in emitted
    assert '__store_i64__(bytes __dewy_array_3)' in emitted
    assert '__store_i64__(2 __dewy_array_3 + 32)' in emitted
    assert '__store_i64__(selected_values __dewy_array_4)' in emitted
    assert 'let overload_result:int64 = read_array(__dewy_array_4)' in emitted
    assert '__dewy_array_data_' not in emitted


def test_keyword_default_fixture_codegen_shape() -> None:
    emitted = codegen(SrcFile.from_path(fixtures / 'keyword_default_calls.dewy'))

    assert '__dewy_default_arg_y_' in emitted
    assert '__dewy_default_has_y_' in emitted
    assert 'if not __dewy_default_has_y_' in emitted
    assert 'let direct:int64 = add(40 0 false)' in emitted
    assert 'let override:int64 = add(39 3 true)' in emitted
    assert 'let reordered:int64 = subtract(42 0)' in emitted
    assert 'let keyword_only:int64 = required(40 2)' in emitted
    assert '...' not in emitted
    assert ' y=' not in emitted


@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_bare_metal_dewy_hello_world(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    emitted = codegen(SrcFile.from_path(fixtures / 'hello_world_syscall.dewy'))
    assert '__load_i64__(message)' in emitted
    assert '__syscall3__(1 1 data 14)' in emitted

    udewy_path = tmp_path / 'hello_world_syscall.udewy'
    udewy_path.write_text(emitted)
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 0
    assert capfd.readouterr().out == 'Hello, World!\n'


@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_no_prelude_import_writes_to_console(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    emitted = codegen(SrcFile.from_path(fixtures / 'no_prelude' / 'main.dewy'))
    assert 'let __dewy_module_prelude_path_p =' in emitted
    assert '__syscall3__(1 1 data 22)' in emitted

    udewy_path = tmp_path / 'no_prelude.udewy'
    udewy_path.write_text(emitted)
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 0
    assert capfd.readouterr().out == 'hello from no_prelude\n'


@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_function_values_lower_to_udewy_indirect_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = repo / 'udewy' / 'tests' / 'test_indirect_call.udewy'
    emitted = codegen(SrcFile.from_path(source_path))

    assert 'let choose = ():><int64:>int64>' in emitted
    assert 'let fn_ptr:<int64:>int64> = choose()' in emitted
    assert 'let indirect:int64 = (fn_ptr)(5)' in emitted
    assert 'let piped:int64 = (fn_ptr)(6)' in emitted

    udewy_path = tmp_path / 'indirect_calls.udewy'
    udewy_path.write_text(emitted)
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 22


@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_reference_udewy_indirect_call_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert entry_point(repo / 'udewy' / 'tests' / 'test_indirect_call.udewy', []) == 22


def test_jump_table_codegen_uses_raw_static_storage() -> None:
    path = fixtures / 'jump_table.dewy'
    emitted = codegen(SrcFile(path, f'$no_prelude = true\n{path.read_text()}'))

    assert (
        'const handlers:int64 = '
        '__static_words__(add_one double add_ten)'
    ) in emitted
    assert 'const program:int64 = 0x"000102"' in emitted
    assert '0q"' not in emitted
    assert '__load_i64__(handlers + (opcode * 8))' in emitted
    assert 'accumulator = (handler)(accumulator)' in emitted
    assert 'alloca__(48)' not in emitted
    assert '__store_i64__(' not in emitted


def test_source_suffix_does_not_affect_typing(tmp_path: Path) -> None:
    source = """let main = ():>int64 => {
    let value:int64 = 40
    return value + 2
}
"""
    dewy_path = tmp_path / 'same.dewy'
    udewy_path = tmp_path / 'same.udewy'
    dewy_path.write_text(source)
    udewy_path.write_text(source)

    assert check.typecheck_and_resolve(SrcFile.from_path(dewy_path)) == check.typecheck_and_resolve(
        SrcFile.from_path(udewy_path)
    )


def test_top_level_codegen_preserves_startup_before_main() -> None:
    emitted = codegen(SrcFile.from_path(fixtures / 'top_level_then_main.dewy'))

    assert 'let value:int64 = 0' in emitted
    assert 'let result:int64 = 0' in emitted
    assert 'let __dewy_user_main = ():>int64' in emitted
    assert 'let __dewy_top_level = ():>void' in emitted
    assert 'let main = ():>int64' in emitted
    startup = emitted.index('let __dewy_top_level')
    assert emitted.index('value = 1', startup) < emitted.index('value = value + 1', startup)
    assert emitted.index('value = value + 1', startup) < emitted.index(
        'result = value + 40',
        startup,
    )
    wrapper = emitted.index('let main = ():>int64')
    assert emitted.index('__dewy_top_level()', wrapper) < emitted.index(
        '__dewy_user_main()',
        wrapper,
    )


def test_fixed_width_right_shift_lowering_is_type_directed(tmp_path: Path) -> None:
    source = """let unsigned = (value:uint64):>uint64 => {
    return value >> 2
}
let main = ():>int64 => {
    let value:int64 = -8
    return value >> 2
}
"""
    path = tmp_path / 'shifts.dewy'
    path.write_text(source)

    emitted = codegen(SrcFile.from_path(path))

    assert 'return value >> 2' in emitted
    assert 'return __signed_shr__(value 2)' in emitted


def test_explicit_signed_shift_intrinsic_roundtrips(tmp_path: Path) -> None:
    source = """let main = ():>int64 => {
    let value:int64 = -8
    return __signed_shr__(value 2)
}
"""
    path = tmp_path / 'intrinsic.udewy'
    path.write_text(source)

    assert codegen(SrcFile(path, f'$no_prelude = true\n{source}')) == source


def test_abstract_integer_right_shift_fails_udewy_lowering(tmp_path: Path) -> None:
    source = """let main = ():>int => {
    let value:int = 8
    return value >> 2
}
"""
    path = tmp_path / 'abstract.dewy'
    path.write_text(source)

    with pytest.raises(NotImplementedError, match='abstract `int` operation'):
        codegen(SrcFile.from_path(path))


@pytest.mark.parametrize(
    ('annotation', 'expression', 'message'),
    [
        ('uint64', 'value // 2', 'unsigned operation'),
        ('int8', 'value + 1', 'rollover operation'),
    ],
)
def test_deferred_fixed_width_lowering_fails_explicitly(
    annotation: str,
    expression: str,
    message: str,
    tmp_path: Path,
) -> None:
    source = f"""let compute = (value:{annotation}):>{annotation} => {{
    return {expression}
}}
let main = ():>{annotation} => compute(8)
"""
    path = tmp_path / 'unsupported.dewy'
    path.write_text(source)

    with pytest.raises(NotImplementedError, match=message):
        codegen(SrcFile.from_path(path))
