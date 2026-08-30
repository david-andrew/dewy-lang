"""Printing values: `print`/`printl` take anything that prints, containers and
objects print as their literal syntax, and `as string` builds the same text."""
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


# ------------------------------------------------------------ what `print` takes

def test_printl_takes_whatever_print_takes() -> None:
    emitted = _main('    printl(5)\n    printl(true)\n    printl(1/2)')
    assert '_print_int64' in emitted and '_print_bool' in emitted and '_print_rational' in emitted


def test_containers_print_through_the_library_printers() -> None:
    emitted = _main('    let xs = [1 2 3]\n    print(xs)\n    printl(set["a"])\n    printl(["k" -> 1])')
    assert '_print_array__int64(' in emitted
    assert '_print_set__string(' in emitted
    assert '_print_dict__string_int64(' in emitted


def test_string_members_are_marked_for_quoting() -> None:
    emitted = _main('    printl(["a" "b"])\n    printl([1 2])')
    assert re.search(r'_print_array__string\w*\(\w+ true\)', emitted)
    assert re.search(r'_print_array__int64\(\w+ false\)', emitted)


def test_printed_interpolations_stream_their_structure_fields() -> None:
    emitted = _main('    let xs = [1 2]\n    printl"{xs} items"')
    assert '_print_array__int64(' in emitted and '_array_as_string' not in emitted


def test_materialized_interpolations_and_as_string_build_the_text() -> None:
    emitted = _main('    let xs = [1 2]\n    let s = "{xs}"\n    let t:string = set[1] as string\n    printl"{s}{t}"')
    assert '_array_as_string__int64(' in emitted and '_set_as_string__int64(' in emitted


def test_objects_print_field_by_field_unless_they_convert() -> None:
    emitted = _main('    let pt = [x=1 name="a"]\n    printl(pt)')
    printer = emitted[emitted.index('let __dewy_print_object_1'):]
    assert '_print_member__int64(' in printer and '_print_member__string(' in printer
    emitted = _compile('let T:type = [v:int64 __as__ = ():>string => "t"]\nlet main = ():>int64 => { printl(T(1))  return 0 }\n')
    assert 'T____as__' in emitted and '__dewy_print_object' not in emitted


def test_nesting_is_arbitrary() -> None:
    emitted = _main('    let pt = [x=1]\n    printl([pt pt])\n    printl([k=[1 2]])')
    assert '__dewy_print_object_1' in emitted and '_print_array__int64(' in emitted


def test_members_that_cannot_print_are_reported_on_the_value() -> None:
    # (a call is one reading of `print(x)`; the readings summary keeps the titles)
    with pytest.raises(UserError, match='this value does not print'):
        _compile('let Slot:type = [v:int64|undefined]\nlet main = ():>int64 => {\n    let slots = [Slot(1)]\n    printl(slots)\n    return 0\n}\n')
    with pytest.raises(TypeCheckError, match='no `print` method takes its member of type `int64 \\| undefined`'):
        _compile('let Slot:type = [v:int64|undefined]\nlet main = ():>int64 => {\n    let slots = [Slot(1)]\n    printl"{slots}"\n    return 0\n}\n')
    with pytest.raises(TypeCheckError, match='containers, which a loop cannot visit yet'):
        _main('    printl"{[[1 2] [3 4]]}"')
    with pytest.raises(TypeCheckError, match='prints but does not convert to string yet'):
        _main('    let r:Rational = 1/2\n    let s:string = [r r] as string')


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
        'let show = <T>(v:T):>int64 => if v is? string v.length else 7\n'
        'let main = ():>int64 => show("abc") + show(1)\n'
    )
    assert 'show__string' in emitted and 'show__int64' in emitted


# ------------------------------------------------------------ the fixes on the way

def test_generics_can_be_called_at_module_level() -> None:
    _compile('let count = <T>(xs:array<T>):>int64 => xs.length\nlet n = count([7 8])\nlet main = ():>int64 => n\n')


def test_a_bare_identifier_signature_is_a_one_parameter_function() -> None:
    root = check.typecheck_and_resolve(SrcFile(None, 'let ignore = s => ()\n'))
    assert root is not None


def test_doc_strings_are_accepted() -> None:
    _compile('doc"""\nA module.\n"""\nlet main = ():>int64 => {\n    doc"the entry"\n    return 0\n}\n')


# ------------------------------------------------------------ the output

@needs_toolchain
def test_printed_text_is_the_literal_syntax(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    source = (
        'let Point:type = [x:int64 y:int64]\n'
        'let main = ():>int64 => {\n'
        '    printl(5)\n'
        '    printl([1 2 3])\n'
        '    printl(set["a\\tb" "c"])\n'
        '    printl(["k" -> Point(1 2)])\n'
        '    printl"{[true false]} and {[name="q"]}"\n'
        '    let text:string = [[x=1 y=2]] as string\n'
        '    printl(text)\n'
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
        '[1 2 3]',
        'set["a\\tb" "c"]',
        '["k" -> [x=1 y=2]]',
        '[true false] and [name="q"]',
        '[[x=1 y=2]]',
    ]
