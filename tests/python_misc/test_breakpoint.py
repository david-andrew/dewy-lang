"""`$breakpoint`: the live bindings are printed and the program stops — at a prompt, or in an attached debugger.
The compiler also marks every emitted statement with its Dewy position for the debugger's line table."""
import subprocess
from pathlib import Path
from shutil import which

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import UserError
from udewy.frontend import EntryPointOptions, entry_point

here = Path(__file__).parent
repo = here.parent.parent

PROGRAM = '''let Hit = type of any & [length:uint64 name:string]
let scale:int64 = 3
let describe = (hits:array<Hit> label:string):>int64 => {
    let total:int64 = 0
    loop h in hits {
        total += (h.length transmute int64) * scale
        let maybe:int64|none = if total >? 10 total else none
        $breakpoint
    }
    return total
}
let main = ():>int64 => {
    let hits:array<Hit> = [Hit[length=3 name="a"] Hit[length=10 name="b"]]
    let r = describe(hits "run")
    $breakpoint
    return 42
}
'''


def _check(source: str) -> hir.AST:
    return check.typecheck_and_resolve(SrcFile(None, source))


def _calls(node: object) -> list[str]:
    names: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, hir.FunctionCall) and isinstance(value.func, hir.ExpressedIdentifier):
            names.append(value.func.name)
        if hasattr(value, '__dataclass_fields__'):
            for name in value.__dataclass_fields__:
                walk(getattr(value, name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(node)
    return names


def test_a_breakpoint_prints_the_functions_bindings_and_traps_or_pauses() -> None:
    checked = _check(PROGRAM)
    names = _calls(checked)
    # prelude names are mangled in the merged program
    assert any(name.endswith('_breakpoint_banner') for name in names) and any(name.endswith('_breakpoint_under_debugger') for name in names)
    assert '__breakpoint__' in names and any(name.endswith('_breakpoint_pause') for name in names)


def test_the_snapshot_shows_the_current_functions_values_only() -> None:
    checked = _check('let outer:int64 = 1\nlet f = (n:int64):>int64 => {\n    let inner = n + 1\n    $breakpoint\n    return inner\n}\n')
    printed = [item.content for item in _strings(checked) if item.content.startswith('  ')]
    assert any(text.startswith('  n = ') for text in printed) and any(text.startswith('  inner = ') for text in printed)
    assert not any(text.startswith('  outer') or text.startswith('  f ') for text in printed)


def _strings(node: object) -> list[hir.String]:
    found: list[hir.String] = []

    def walk(value: object) -> None:
        if isinstance(value, hir.String):
            found.append(value)
        if hasattr(value, '__dataclass_fields__'):
            for name in value.__dataclass_fields__:
                walk(getattr(value, name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(node)
    return found


def test_a_breakpoint_takes_no_argument() -> None:
    with pytest.raises(UserError):
        _check('let main = ():>int64 => {\n    $breakpoint 1\n    return 0\n}\n')


def test_emitted_statements_carry_their_dewy_positions(tmp_path: Path) -> None:
    source = tmp_path / 'located.dewy'
    source.write_text('let square = (n:int64):>int64 => n * n\nlet main = ():>int64 => {\n    let total:int64 = square(3)\n    return total\n}\n')
    emitted = codegen(SrcFile.from_path(source))
    assert f'# @loc {source.resolve()}:3:5' in emitted and f'# @loc {source.resolve()}:4:5' in emitted
    assert f'# @loc {source.resolve()}:1:34' in emitted     # the expression body of `square`


@pytest.mark.skipif(which('as') is None or which('ld') is None, reason='needs the x86_64 toolchain')
def test_a_breakpoint_holds_the_program_at_a_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / 'stops.dewy'
    source.write_text(PROGRAM)
    udewy_path = tmp_path / 'stops.udewy'
    udewy_path.write_text(codegen(SrcFile.from_path(source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, [], EntryPointOptions(compile_only=True)) == 0
    binary = tmp_path / '__dewycache__' / 'stops'
    # `\h` lists the commands, an expression is refused, `\c` continues; the remaining stops read end of input and continue
    result = subprocess.run([str(binary)], input=b'\\h\nfoo\n\\c\n', capture_output=True, timeout=60)
    assert result.returncode == 42
    text = result.stdout.decode()
    assert text.count('── breakpoint at stops.dewy:8 ──') == 2 and '── breakpoint at stops.dewy:15 ──' in text
    assert '  label = "run"' in text and '  total = 9' in text and '  maybe = none' in text and '  maybe = 39' in text
    assert '  r = 39' in text
    assert '\\c  continue' in text and 'expressions cannot be evaluated here yet' in text
    # `\q` ends the program
    result = subprocess.run([str(binary)], input=b'\\q\n', capture_output=True, timeout=60)
    assert result.returncode == 130 and result.stdout.decode().count('── breakpoint') == 1


@pytest.mark.skipif(which('as') is None or which('ld') is None, reason='needs the x86_64 toolchain')
def test_a_decoded_string_survives_being_returned_in_an_optional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # regression: the decoded string lived in the function's string region, released on exit
    source = tmp_path / 'decoded.dewy'
    source.write_text(
        'let read = ():>string|none => {\n    let bytes:array<uint8> = [32 120 32]\n    return bytes as string|none\n}\n'
        'let shout = (text:string):>string => "<{text}>"\n'
        'let main = ():>int64 => {\n    match read() {\n        <none> => return 1\n        line:string => {\n'
        '            if shout(line) =? "< x >" and line.trim =? "x" { return 42 }\n            return 2\n        }\n    }\n}\n'
    )
    udewy_path = tmp_path / 'decoded.udewy'
    udewy_path.write_text(codegen(SrcFile.from_path(source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 42


def test_a_debug_build_names_each_variables_type_and_formatter(tmp_path: Path) -> None:
    source = tmp_path / 'values.dewy'
    source.write_text(PROGRAM)
    plain = codegen(SrcFile.from_path(source))
    assert '# @var total - - int64\n' in plain and '__dewy_debug_show_' not in plain      # types, no formatters
    debug = codegen(SrcFile.from_path(source), debug_values=True)
    lines = debug.splitlines()
    markers = {line.split()[2]: line.split()[3:] for line in lines if line.strip().startswith('# @var') and len(line.split()) > 4}
    assert markers['hits'][1].startswith('__dewy_debug_show_')                       # a parameter's formatter
    assert markers['label'][1].startswith('__dewy_debug_show_') and markers['maybe'][1].startswith('__dewy_debug_show_')
    assert markers['maybe'][2:] == ['int64', '|', 'none']
    loop_variable = next(line for line in lines if line.strip().startswith('# @var __dewy_iterator_value'))
    assert loop_variable.split()[3] == 'h' and loop_variable.split()[5] == 'Hit'      # the loop variable, shown as `h`
    assert '__dewy_debug_show_raw_0' in debug                                          # main's `hits` is raw frame data: a descriptor thunk
    assert 'const __dewy_debug_formatters:int64 = __static_words__(' in debug          # the formatters stay reachable
    assert 'let __dewy_debug_show_' in debug


def test_arrays_of_fixed_length_strings_print() -> None:
    _check('let main = ():>int64 => {\n    let words = ["x" "y"]\n    printl"{words}"\n    return 0\n}\n')   # `array<string<length=1> length=2>` reads as `array<string>`


@pytest.mark.skipif(which('as') is None or which('ld') is None or which('lldb') is None, reason='needs the x86_64 toolchain and lldb')
def test_lldb_shows_dewy_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / 'shown.dewy'
    source.write_text(PROGRAM)
    udewy_path = tmp_path / 'shown.udewy'
    udewy_path.write_text(codegen(SrcFile.from_path(source), debug_values=True))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, [], EntryPointOptions(compile_only=True)) == 0
    binary = tmp_path / '__dewycache__' / 'shown'
    script = tmp_path / 'session.lldb'
    script.write_text(f'command script import {repo / "tools" / "dewy_lldb.py"}\nb shown.dewy:8\nrun\nframe variable\nup\nframe variable\nq\n')
    result = subprocess.run(['lldb', '--batch', '-s', str(script), str(binary)], capture_output=True, timeout=120, text=True)
    text = result.stdout
    assert '(array<Hit>) hits = [Hit[length=3 name="a"] Hit[length=10 name="b"]]' in text
    assert '(string) label = "run"' in text and '(int64 | none) maybe = none' in text and '(int64) total = 9' in text
    assert '(Hit) h = Hit[length=3 name="a"]' in text
    caller = text[text.rindex('frame variable'):]
    assert '(array<Hit length=2>) hits = [Hit[length=3 name="a"] Hit[length=10 name="b"]]' in caller   # raw frame data, through the thunk
    assert ' r = ' not in caller                                                                    # not declared yet at the call


@pytest.mark.skipif(which('as') is None or which('ld') is None or which('gdb') is None, reason='needs the x86_64 toolchain and gdb')
def test_gdb_shows_dewy_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / 'shown.dewy'
    source.write_text(PROGRAM)
    udewy_path = tmp_path / 'shown.udewy'
    udewy_path.write_text(codegen(SrcFile.from_path(source), debug_values=True))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, [], EntryPointOptions(compile_only=True)) == 0
    binary = tmp_path / '__dewycache__' / 'shown'
    script = tmp_path / 'session.gdb'
    script.write_text('set pagination off\nbreak shown.dewy:8\nrun\ninfo args\ninfo locals\nprint total\nup\ninfo locals\ncontinue\nbt 2\nquit\n')
    result = subprocess.run(['gdb', '-q', '-batch', '-x', str(repo / 'tools' / 'dewy_gdb.py'), '-x', str(script), str(binary)], capture_output=True, timeout=120, text=True)
    text = result.stdout + result.stderr
    assert 'hits = [Hit[length=3 name="a"] Hit[length=10 name="b"]]' in text and 'label = "run"' in text   # `info args`
    assert 'total = 9' in text and 'maybe = none' in text and 'h = Hit[length=3 name="a"]' in text
    assert '$1 = 9' in text
    assert 'describe (hits=[Hit[length=3 name="a"] Hit[length=10 name="b"]], label="run") at' in text   # frames show their arguments
    assert 'Program received signal SIGTRAP' in text and '__dewy_user_main () at' in text                  # `$breakpoint` traps
