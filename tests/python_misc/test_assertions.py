"""`$assert` (compile-time obligation) and `$runtime_assert` (checked at runtime, diverges on failure)."""

from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import UserError, TypeCheckError
from udewy.frontend import entry_point

from test_cleanparse_udewy_e2e import x86_64_toolchain_available

fixtures = Path(__file__).resolve().parents[2] / 'dewy' / 'tests'

RED, CYAN, GREY, RESET = '\x1b[31m', '\x1b[96m', '\x1b[38;5;245m', '\x1b[0m'


def _expected_report(path: Path, row: int, column: int, line: str, width: int, message: str, notes: list[str], *, color: bool = False) -> str:
    """The stderr of a failed `$runtime_assert`, in the compiler's report layout (uncolored: the captured stream is not a terminal)."""
    red, cyan, grey, reset = (RED, CYAN, GREY, RESET) if color else ('', '', '', '')
    gutter = ' ' * (3 + len(str(row)))
    middle = (width - 1) // 2
    underline = '─' * middle + '┬' + '─' * (width - 1 - middle)
    out = [
        f'Error: {red}assertion failed{reset}',
        '',
        f'{gutter}╭─[{path}:{row}:{column}]',
        f'  {grey}{row}{reset} | {line}',
        f'{gutter}·{" " * column}{cyan}{underline}{reset}',
        f'{gutter}·{" " * (column + middle)}{cyan}╰─ {message}{reset}',
        f'{gutter}╰───',
    ]
    for index, note in enumerate(notes):
        out.append((f'  {grey}note:{reset} ' if index == 0 else '        ') + note)
    return '\n'.join(out) + '\n'


def _compile(source: str) -> str:
    """Typecheck, analyze (bounds validation included), and lower to µDewy."""
    return codegen(SrcFile(None, source))


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, '$no_prelude = true\n' + source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_proven_assertions_compile_to_nothing() -> None:
    emitted = _compile(
        'let xs:array<int64> = [1 2 3]\n'
        '$assert 1 + 1 =? 2\n'
        '$assert xs.length =? 3, "three elements"\n'
        '$assert "ab" =? "ab"\n'
        'let main = ():>int64 => { let x:int64 = 3  $assert x <? 5  loop i in 0..2 { $assert i <? 3 }  return 0 }\n'
    )
    assert 'assert' not in emitted


def test_unknown_assertion_is_reported_as_unproven() -> None:
    with pytest.raises(UserError, match='cannot prove assertion') as info:
        _compile('let f = (x:int64):>int64 => { $assert x <? 3  return x }\n')
    assert 'neither proven nor refuted' in str(info.value)
    assert '`$runtime_assert`' in str(info.value)


def test_refuted_assertions_are_errors() -> None:
    with pytest.raises(UserError, match='assertion refuted'):
        _compile('$assert 1 =? 2\n')
    with pytest.raises(UserError, match='assertion refuted') as info:
        _compile('let xs:array<int64> = [1 2]\n$assert xs.length =? 3, "three elements expected"\n')
    assert 'three elements expected' in str(info.value)
    with pytest.raises(UserError, match='assertion refuted'):
        _compile('let main = ():>int64 => { $runtime_assert 1 >? 2  return 0 }\n')


def test_assertion_forms_are_validated() -> None:
    with pytest.raises(UserError, match='needs a condition'):
        _compile('$assert\nlet main = ():>int64 => 0\n')
    with pytest.raises(UserError, match='must be a string literal'):
        _compile('let x:int64 = 3\n$assert x =? 3, "x is {x}"\n')
    with pytest.raises(UserError, match='at most one message'):
        _compile('let x:int64 = 3\n$assert x =? 3, "a", "b"\n')
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _compile('let main = ():>int64 => { $runtime_assert 5  return 0 }\n')


def test_runtime_assertion_facts_flow_to_the_code_after_it() -> None:
    _compile(
        'let get = (ys:array<int64> i:int64):>int64 => {\n'
        '    $runtime_assert i >=? 0 and i <? ys.length, "index {i} out of range"\n'
        '    return ys[i]\n'
        '}\n'
        'let describe = (v:int64|string):>int64 => { $runtime_assert v is? int64  return v + 1 }\n'
    )
    with pytest.raises(UserError, match='array index is not proven'):
        _compile('let get = (ys:array<int64> i:int64):>int64 => { $runtime_assert i >=? 0  return ys[i] }\n')


def test_diverging_branches_prove_the_continuation() -> None:
    # a pre-existing gap surfaced by the first assertions: the bounds analysis
    # joined every arm of a conditional even when one diverged
    _compile(
        'let get = (ys:array<int64> i:int64):>int64 => {\n'
        '    if i <? 0 or i >=? ys.length { return 0 }\n'
        '    return ys[i]\n'
        '}\n'
    )
    _compile(
        'let first_big = (ys:array<int64>):>int64 => {\n'
        '    let i:int64 = 0\n'
        '    loop i <? ys.length {\n'
        '        if ys[i] >? 10 { return i }\n'
        '        i += 1\n'
        '    }\n'
        '    return -1\n'
        '}\n'
    )


def test_same_singleton_twice_widens_the_operation_type() -> None:
    declared = _declared('let a = 1 + 1\nlet b = 2 - 2\n')
    assert declared['a'].expr.type == 'int'
    assert declared['b'].expr.type == 'int'


@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_failed_runtime_assertion_reports_to_stderr_and_exits_101(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / 'fail.dewy'
    source.write_text(
        'let check = (x:int64 limit:int64):>int64 => {\n'
        '    $runtime_assert x <? limit and x not=? 4, "x must stay below {limit}"\n'
        '    return x\n'
        '}\n'
        'let main = ():>int64 => {\n'
        '    printl"before"\n'
        '    let r:int64 = check(5 3)\n'
        '    printl"after"\n'
        '    return r\n'
        '}\n'
    )
    udewy_path = tmp_path / 'fail.udewy'
    udewy_path.write_text(codegen(SrcFile.from_path(source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 101
    captured = capfd.readouterr()
    assert captured.out == 'before\n'
    assert captured.err == _expected_report(
        source, 2, 21,
        '    $runtime_assert x <? limit and x not=? 4, "x must stay below {limit}"',
        len('x <? limit and x not=? 4'),
        'x must stay below 3',
        ['`x` is 5', '`limit` is 3'],
    )


def test_failing_fixtures_report_refuted_and_unproven_assertions() -> None:
    with pytest.raises(UserError, match='assertion refuted') as info:
        codegen(SrcFile.from_path(fixtures / 'assertions_refuted.dewy'))
    report = str(info.value)
    assert 'the index must stay inside the array' in report
    assert '`i` is 3' in report
    assert '`xs.length` is 3 (the array has exactly 3 elements)' in report
    assert 'so `i <? xs.length` is false' in report
    with pytest.raises(UserError, match='cannot prove assertion') as info:
        codegen(SrcFile.from_path(fixtures / 'assertions_unproven.dewy'))
    report = str(info.value)
    assert '`i` has no known bound' in report
    assert '`ys.length` is a runtime length of at least 0' in report
    assert '`i <? ys.length` cannot be decided from these facts' in report


@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_failing_runtime_fixture_reports_operands_and_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source = fixtures / 'assertions_runtime_fail.dewy'
    udewy_path = tmp_path / 'assertions_runtime_fail.udewy'
    udewy_path.write_text(codegen(SrcFile.from_path(source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 101
    captured = capfd.readouterr()
    assert captured.out == 'after 10: 20\n'
    assert captured.err == _expected_report(
        source, 7, 21,
        '    $runtime_assert amount >? 0 and amount <=? account.balance, "cannot withdraw {amount} from {account.name}"',
        len('amount >? 0 and amount <=? account.balance'),
        'cannot withdraw 50 from alice',
        ['`amount` is 50', '`account.balance` is 30'],
    )


def test_report_colors_follow_the_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    from dewy.reporting import Error, Pointer, Span, color_enabled

    class Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.delenv('NO_COLOR', raising=False)
    assert color_enabled(Terminal())
    assert not color_enabled(io.StringIO())
    monkeypatch.setenv('NO_COLOR', '1')
    assert not color_enabled(Terminal())
    srcfile = SrcFile(None, 'let x = 1\n')
    report = Error(srcfile=srcfile, title='plain', pointer_messages=[Pointer(span=Span(4, 5), message='here')], use_color=False)
    assert '\x1b[' not in str(report)


def test_assertion_messages_are_dimmed_in_colored_reports() -> None:
    with pytest.raises(UserError) as info:
        codegen(SrcFile.from_path(fixtures / 'assertions_refuted.dewy'))
    report = info.value.report
    assert report.dimmed and report.srcfile.body[report.dimmed[0].start:report.dimmed[0].stop] == ', "the index must stay inside the array"'
    report.use_color = True
    assert '\x1b[90m, "the index must stay inside the array"\x1b[0m' in str(report)
    report.use_color = False
    assert '$assert i <? xs.length, "the index must stay inside the array"' in str(report)


@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_reporting_library_matches_the_compiler_renderer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    from dewy.reporting import Error, Pointer, Span

    excerpt = 'let total = price * count + tax\nlet other = 1'
    expected = str(Error(
        srcfile=SrcFile(None, excerpt + '\n'),
        title='sample',
        message='two pointers on one line',
        pointer_messages=[
            Pointer(span=Span(12, 17), message='first operand'),
            Pointer(span=Span(20, 25), message='second operand'),
            Pointer(span=Span(36, 41), message='next line'),
        ],
        notes=['a note', 'another'],
        hint='hint',
        use_color=False,
    )) + '\n'
    udewy_path = tmp_path / 'report_layout.udewy'
    udewy_path.write_text(codegen(SrcFile.from_path(fixtures / 'report_layout.dewy')))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 42
    assert capfd.readouterr().err == expected
