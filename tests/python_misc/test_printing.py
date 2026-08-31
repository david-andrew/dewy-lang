"""Printing values: `print`/`printl` are library generics that print a value by
its type and anything else as its `as string` text; containers and objects
convert to their literal syntax."""
import re
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import TypeCheckError, UserError
from udewy.frontend import entry_point

from test_cleanparse_udewy_e2e import x86_64_toolchain_available

needs_toolchain = pytest.mark.skipif(not x86_64_toolchain_available(), reason='needs the x86_64 toolchain')


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def _main(body: str) -> str:
    return _compile('let main = ():>int64 => {\n' + body + '\n    return 0\n}\n')


# ------------------------------------------------------------ print by type

def test_print_is_instantiated_per_argument_type_and_picks_its_arm() -> None:
    emitted = _main('    printl(5)\n    printl(true)\n    printl(1/2)\n    let b:uint8 = 3\n    print(b)')
    # (an instance is hoisted into the module that first needs it — `print__int64` into the prelude)
    assert 'print__int64 = (value:int64):>void => {' in emitted and '_print_int64(' in emitted.split('print__int64 = ')[1].split('\nlet ')[0]
    assert 'print__bool = ' in emitted and 'let printl__bool ' in emitted
    assert 'let print__uint8 ' in emitted
    assert 'let print__BigRational ' in emitted or '_print_bigrational(' in emitted   # `1/2` binds the runtime rational


def test_containers_convert_through_the_library_shapes() -> None:
    emitted = _main('    let xs = [1 2 3]\n    print(xs)\n    printl(set["ab"])\n    printl(["k" -> 1])')
    assert '_array_as_string__int64(' in emitted
    assert '_set_as_string__string(' in emitted
    assert '_dict_as_string__string_int64(' in emitted


def test_string_members_are_marked_for_quoting() -> None:
    emitted = _main('    printl(["ab" "cd"])\n    printl([1 2])')
    assert re.search(r'_array_as_string__string\w*\(\w+ true\)', emitted)
    assert re.search(r'_array_as_string__int64\(\w+ false\)', emitted)


def test_grapheme_arrays_convert_to_their_text() -> None:
    # `array<char> as string` is the text the graphemes form, and printing is `as string`
    emitted = _main('    printl(["a" "b"])')
    assert '_array_as_string' not in emitted


def test_printed_interpolations_are_written_part_by_part() -> None:
    emitted = _main('    let xs = [1 2]\n    printl"{xs} items"')
    body = emitted.split('let __dewy_user_main')[1]
    assert len(re.findall(r'print__string(?:_\d+)?\(', body)) >= 2 and '_array_as_string__int64(' in emitted


def test_materialized_interpolations_and_as_string_build_the_text() -> None:
    emitted = _main('    let xs = [1 2]\n    let s = "{xs}"\n    let t:string = set[1] as string\n    printl"{s}{t}"')
    assert '_array_as_string__int64(' in emitted and '_set_as_string__int64(' in emitted


def test_objects_convert_field_by_field_unless_they_declare_a_conversion() -> None:
    emitted = _main('    let pt = [x=1 name="a"]\n    printl(pt)')
    conversion = emitted[emitted.index('let __dewy_object_string_1'):]
    assert '_quoted(' in conversion and '.join' in conversion or 'pieces' in conversion
    emitted = _compile('let T:type = [v:int64 __as__ = ():>string => "t"]\nlet main = ():>int64 => { printl(T(1))  return 0 }\n')
    assert 'T____as__' in emitted and '__dewy_object_string' not in emitted


def test_nesting_is_arbitrary() -> None:
    emitted = _main('    let pt = [x=1]\n    printl([pt pt])\n    printl([k=[1 2]])')
    assert '__dewy_object_string_1' in emitted and '_array_as_string__int64(' in emitted


def test_values_that_cannot_convert_are_reported_on_the_value() -> None:
    with pytest.raises(TypeCheckError, match='containers, which a loop cannot visit yet'):
        _main('    printl"{[[1 2] [3 4]]}"')
    with pytest.raises(TypeCheckError, match='`Rational` prints, but has no string form yet'):
        _main('    let r:Rational = 1/2\n    let s:string = r as string')
    with pytest.raises(TypeCheckError, match='does not convert to string|no `print` method takes'):
        _compile('let Holder:type = [f:(n:int64):>int64]\nlet main = ():>int64 => {\n    let h = Holder((n:int64):>int64 => n)\n    printl"{h}"\n    return 0\n}\n')


def test_optionals_print() -> None:
    # `int64 | none` prints — alone, in containers, and as a field
    _main('    let opt:int64|none = 1\n    printl(opt)\n    let xs:array<int64|none> = [opt none]\n    printl(xs)\n    printl"{opt}"')
    _compile('let Slot:type = [v:int64|none]\nlet main = ():>int64 => {\n    let slots = [Slot(1)]\n    printl"{slots}"\n    return 0\n}\n')


# ------------------------------------------------------------ decided type tests

def test_a_type_test_the_static_type_settles_is_decided() -> None:
    root = check.typecheck_and_resolve(SrcFile(None, 'let f = (v:int64):>int64 => if v is? string 1 else 2\n'))
    f = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'f')
    body = f.expr.body
    while isinstance(body, hir.Block) and len(body.items) == 1:
        body = body.items[0]
    # the dead arm is gone; the flow is its `else`
    assert isinstance(body, hir.Integer) and body.value == 2


def test_a_generic_dispatches_on_its_type_parameter_with_a_type_test() -> None:
    emitted = _compile(
        'let size = <T>(v:T):>int64 => if v is? string v.length else 7\n'
        'let main = ():>int64 => size("abc") + size(1)\n'
    )
    assert 'size__string' in emitted and 'size__int64' in emitted


# ------------------------------------------------------------ the fixes on the way

def test_generics_can_be_called_at_module_level() -> None:
    _compile('let count = <T>(xs:array<T>):>int64 => xs.length\nlet n = count([7 8])\nlet main = ():>int64 => n\n')


def test_a_bare_identifier_signature_is_a_one_parameter_function() -> None:
    root = check.typecheck_and_resolve(SrcFile(None, 'let ignore = s => ()\n'))
    assert root is not None


def test_doc_strings_are_accepted() -> None:
    _compile('doc"""\nA module.\n"""\nlet main = ():>int64 => {\n    doc"the entry"\n    return 0\n}\n')


def test_one_substantive_reading_reports_its_own_error() -> None:
    with pytest.raises(TypeCheckError, match='no string conversion for this value'):
        _compile('let Holder:type = [f:(n:int64):>int64]\nlet main = ():>int64 => { let h = Holder((n:int64):>int64 => n)  let t:string = h as string  return 0 }\n')
    with pytest.raises(UserError) as caught:   # the readings' verdict is definite, with the one reading's own message
        _main('    printl([[1 2] [3 4]])')
    assert 'no valid interpretation' not in str(caught.value) and 'containers, which a loop cannot visit' in str(caught.value)


# ------------------------------------------------------------ the output

@needs_toolchain
def test_printed_text_is_the_literal_syntax(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    source = (
        'let Point:type = [x:int64 y:int64]\n'
        'let main = ():>int64 => {\n'
        '    printl(5)\n'
        '    let b:uint8 = 200\n'
        '    printl(b)\n'
        '    printl([1 2 3])\n'
        '    printl(set["a\\tb" "c"])\n'
        '    printl(["k" -> Point(1 2)])\n'
        '    printl"{[true false]} and {[name="q"]} and {1/3}"\n'
        '    let text:string = [[x=1 y=2]] as string\n'
        '    printl(text)\n'
        '    printl(["a" "b"])\n'
        '    return 0\n'
        '}\n'
    )
    udewy_path = tmp_path / 'printing.udewy'
    udewy_path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 0
    out, _ = capfd.readouterr()
    assert out.splitlines() == [
        '5',
        '200',
        '[1 2 3]',
        'set["a\\tb" "c"]',
        '["k" -> [x=1 y=2]]',
        '[true false] and [name="q"] and 1/3',
        '[[x=1 y=2]]',
        'ab',
    ]
