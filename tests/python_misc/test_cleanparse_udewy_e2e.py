from pathlib import Path
from shutil import which

import pytest

from src.cleanparse.reporting import SrcFile
from src.cleanparse.backend.udewy import codegen
from src.cleanparse.semantic import check
from udewy.frontend import entry_point

here = Path(__file__).parent
fixtures = here.parent.parent / 'src' / 'cleanparse' / 'tests'


def x86_64_toolchain_available() -> bool:
    return which('as') is not None and which('ld') is not None


CASES = [
    ('minimal2.udewy', 42),
    ('arith_locals.udewy', 42),
    ('direct_calls.udewy', 42),
    ('assign_basic.udewy', 42),
    ('div_mod_scalar.udewy', 0),
]
FIXTURE_NAMES = [fixture_name for fixture_name, _ in CASES]


@pytest.mark.parametrize('fixture_name', FIXTURE_NAMES)
def test_udewy_fixture_roundtrip(fixture_name: str) -> None:
    path = fixtures / fixture_name
    source = path.read_text()
    assert codegen(SrcFile.from_path(path)) == source


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

    assert codegen(SrcFile.from_path(path)) == source


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
    source = f"""let main = (value:{annotation}):>{annotation} => {{
    return {expression}
}}
"""
    path = tmp_path / 'unsupported.dewy'
    path.write_text(source)

    with pytest.raises(NotImplementedError, match=message):
        codegen(SrcFile.from_path(path))
