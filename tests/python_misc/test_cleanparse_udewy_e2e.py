from pathlib import Path
from shutil import which

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import TypeCheckError
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
    ('array_returns.dewy', 42),
    ('recursive_returns.dewy', 42),
    ('array_iteration.dewy', 42),
    ('array_value_semantics.dewy', 42),
    ('array_places.dewy', 42),
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
    ('position_only_calls.dewy', 42),
    ('path_values.dewy', 42),
    ('hello_world_syscall.dewy', 0),
    ('hello.dewy', 0),
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
    assert 'let alias:int64 = __alloca__(16)' in emitted
    assert 'let transitive:int64 = __alloca__(16)' in emitted
    assert 'let alias:int64 = local' not in emitted
    assert 'let transitive:int64 = alias' not in emitted
    assert emitted.count('__alloca__(16)') == 6
    assert emitted.count('__alloca__(48)') == 4
    assert '__store_i64__(__load_i64__(transitive) __load_i64__(__dewy_array_1))' in emitted
    assert '__store_i64__(__load_i64__(words) __load_i64__(__dewy_array_3))' in emitted
    assert '__store_i64__(bytes __dewy_array_5)' in emitted
    assert '__store_i64__(2 __dewy_array_5 + 32)' in emitted
    assert '__store_i64__(selected_values __dewy_array_6)' in emitted
    assert 'let overload_result:int64 = read_array(__dewy_array_6)' in emitted
    assert 'local_result =? 42 and __load_i64__(local) =? 0' in emitted


def test_array_value_semantics_fixture_copies_mutable_bindings() -> None:
    emitted = codegen(SrcFile.from_path(fixtures / 'array_value_semantics.dewy'))

    assert 'let copy:int64 = original' not in emitted
    assert 'let transitive:int64 = copy' not in emitted
    assert 'let snapshot:int64 = copy' not in emitted
    assert '__dewy_array_copy_length_' in emitted
    assert '__alloca__(__dewy_array_copy_length_' in emitted
    assert 'loop __dewy_array_copy_index_' in emitted


def test_keyword_default_fixture_codegen_shape() -> None:
    emitted = codegen(SrcFile.from_path(fixtures / 'keyword_default_calls.dewy'))

    assert '__dewy_default_arg_y_' in emitted
    assert '__dewy_default_has_y_' in emitted
    assert 'if not __dewy_default_has_y_' in emitted
    assert 'let direct:int64 = add(40 0 false)' in emitted
    assert 'let positional_default:int64 = interleaved(20 2 true 20)' in emitted
    assert 'let omitted_default:int64 = interleaved(20 0 false 20)' in emitted
    assert 'let named_then_positional:int64 = interleaved(20 2 true 20)' in emitted
    assert 'let override:int64 = add(39 3 true)' in emitted
    assert 'let positional_override:int64 = add(39 3 true)' in emitted
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
def test_prelude_printl_writes_to_console(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    emitted = codegen(SrcFile.from_path(fixtures / 'hello.dewy'))
    assert 'let __dewy_module_prelude_io_print' in emitted
    assert 'let __dewy_module_prelude_io_printl' in emitted

    udewy_path = tmp_path / 'hello.udewy'
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
    assert '__syscall3__(1 1 data 22)' in emitted
    assert 'let __dewy_module_prelude_io_print' not in emitted

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

    assert 'let choose = ():><(x:int64):>int64>' in emitted
    assert 'let fn_ptr:<(x:int64):>int64> = choose()' in emitted
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

    assert '= (__dewy_shift_value_1 >> __dewy_shift_count_2)' in emitted
    assert '__signed_shr__(__dewy_shift_value_3 __dewy_shift_count_4)' in emitted


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
    'annotation',
    ['int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64'],
)
@pytest.mark.parametrize('operator', ['<<', '>>'])
def test_fixed_width_shifts_emit_explicit_width_guard(
    annotation: str,
    operator: str,
) -> None:
    source = f"""let compute = (value:{annotation}):>{annotation} => {{
    return value {operator} 1
}}
let main = ():>{annotation} => compute(8)
"""
    emitted = codegen(SrcFile(None, source))

    width = int(annotation.removeprefix('uint').removeprefix('int'))
    assert '__dewy_shift_count_' in emitted
    assert f' {width})' in emitted
    assert '__unsigned_gte__(' in emitted
    assert '= 0' in emitted


def test_fixed_width_shift_operands_are_each_evaluated_once() -> None:
    emitted = codegen(SrcFile(None, '''
let next_value = ():>uint8 => 1
let next_count = ():>uint64 => 8
let shifted = ():>uint8 => next_value() << next_count()
'''))

    assert emitted.count('= next_value()') == 1
    assert emitted.count('= next_count()') == 1


@pytest.mark.parametrize('source', [
    'let shifted = ():>uint8 => 1 << -1',
    'let shifted = (value:uint8 count:int64):>uint8 => value << count',
])
def test_potentially_negative_shift_count_is_rejected_during_typechecking(
    source: str,
) -> None:
    with pytest.raises(TypeCheckError, match='shift count must be unsigned'):
        codegen(SrcFile(None, source))


@pytest.mark.parametrize(('annotation', 'expected'), [
    ('int8', '__signed_shr__((value + value) << 56 56)'),
    ('int16', '__signed_shr__((value + value) << 48 48)'),
    ('int32', '__signed_shr__((value + value) << 32 32)'),
    ('uint8', '(value + value) and 255'),
    ('uint16', '(value + value) and 65535'),
    ('uint32', '(value + value) and 4294967295'),
])
def test_narrow_integer_width_controls_rollover_lowering(
    annotation: str,
    expected: str,
) -> None:
    emitted = codegen(SrcFile(None, f'''
let double = (value:{annotation}):>{annotation} => value + value
'''))

    assert expected in emitted


@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_fixed_width_rollover_and_unsigned_operations_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = '''
let unsigned_divide = (value:uint64 divisor:uint64):>uint64 => value // divisor
let unsigned_modulo = (value:uint64 divisor:uint64):>uint64 => value % divisor
let add_byte = (value:uint8 amount:uint8):>uint8 => value + amount
let subtract_byte = (value:uint8 amount:uint8):>uint8 => value - amount
let add_signed_byte = (value:int8 amount:int8):>int8 => value + amount
let multiply_signed_byte = (value:int8 amount:int8):>int8 => value * amount
let divide_signed_byte = (value:int8 divisor:int8):>int8 => value // divisor
let modulo_signed_byte = (value:int8 divisor:int8):>int8 => value % divisor
let nand_byte = (value:uint8 mask:uint8):>uint8 => value nand mask
let negate_signed_byte = (value:int8):>int8 => -value
let invert_byte = (value:uint8):>uint8 => not value
let shift_byte_left = (value:uint8 count:uint64):>uint8 => value << count
let shift_byte_right = (value:uint8 count:uint64):>uint8 => value >> count
let shift_signed_byte_left = (value:int8 count:uint64):>int8 => value << count
let shift_signed_byte_right = (value:int8 count:uint64):>int8 => value >> count
let shift_word_left = (value:uint64 count:uint64):>uint64 => value << count
let shift_signed_word_right = (value:int64 count:uint64):>int64 => value >> count

let main = ():>int64 => {
    let high:uint64 = 18446744073709551615
    if unsigned_divide(high 2) =? 9223372036854775807
        and unsigned_modulo(high 2) =? 1
        and high >? 1
        and 1 <? high
        and high >=? high
        and 1 <=? high
        and add_byte(250 10) =? 4
        and subtract_byte(1 2) =? 255
        and add_signed_byte(127 1) =? -128
        and multiply_signed_byte(64 2) =? -128
        and divide_signed_byte(value=-128 divisor=-1) =? -128
        and modulo_signed_byte(value=-128 divisor=-1) =? 0
        and nand_byte(255 15) =? 240
        and negate_signed_byte(-128) =? -128
        and invert_byte(0) =? 255
        and shift_byte_left(1 7) =? 128
        and shift_byte_left(1 8) =? 0
        and shift_byte_left(1 9) =? 0
        and shift_byte_left(255 1) =? 254
        and shift_byte_right(255 7) =? 1
        and shift_byte_right(255 8) =? 0
        and shift_signed_byte_left(64 1) =? -128
        and shift_signed_byte_left(64 8) =? 0
        and shift_signed_byte_right(value=-128 count=7) =? -1
        and shift_signed_byte_right(value=-128 count=8) =? -1
        and shift_signed_byte_right(127 8) =? 0
        and shift_word_left(1 63) =? 9223372036854775808
        and shift_word_left(1 64) =? 0
        and shift_signed_word_right(value=-1 count=63) =? -1
        and shift_signed_word_right(value=-1 count=64) =? -1 {
        return 42
    } else {
        return 1
    }
}
'''
    dewy_path = tmp_path / 'fixed_width.dewy'
    dewy_path.write_text(source)
    emitted = codegen(SrcFile.from_path(dewy_path))

    assert '__unsigned_idiv__(value divisor)' in emitted
    assert '__unsigned_mod__(value divisor)' in emitted
    assert '__unsigned_gt__(high 1)' in emitted
    assert '__unsigned_lt__(1 high)' in emitted
    assert '__unsigned_gte__(high high)' in emitted
    assert '__unsigned_lte__(1 high)' in emitted
    assert '(value + amount) and 255' in emitted
    assert '__signed_shr__((value + amount) << 56 56)' in emitted
    assert '__unsigned_gte__(' in emitted

    udewy_path = tmp_path / 'fixed_width.udewy'
    udewy_path.write_text(emitted)
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 42
