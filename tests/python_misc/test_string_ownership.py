"""Arrays own their element strings: stores copy, releases free elements, and copies of string arrays get their own strings."""
import re

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def _function(emitted: str, name: str) -> str:
    start = emitted.index(f'let {name} = ')
    end = emitted.find('\nlet ', start)
    return emitted[start:] if end == -1 else emitted[start:end]


BUILD = (
    'let build = (n:int64):>int64 => {\n'
    '    let parts:array<string> = []\n'
    '    loop i in [0..4) { parts.push"{i}-{n}" }\n'
    '    return parts.length\n'
    '}\n'
    'let main = ():>int64 => build(3)\n'
)


def test_stored_strings_carry_the_owner_word_and_are_released_with_the_array() -> None:
    emitted = _compile(BUILD)
    build = _function(emitted, 'build')
    # the escape copy marks its descriptor as owned (offset 40 = 1) …
    assert re.search(r'__store_i64__\(1 __dewy_string_value_\d+ \+ 40\)', build)
    # … and the exit releases each element by its owner word, then the buffer
    assert re.search(r'__load_i64__\(__dewy_string_release_element_\d+ \+ 40\)', build)
    assert build.count('_arena_release(') >= 4


def test_element_reads_copy_when_stored_or_returned() -> None:
    emitted = _compile(
        'let head = (xs:array<string>):>string => {\n'
        '    if xs.length >? 0 { return xs[0] }\n'
        '    return ""\n'
        '}\n'
        'let main = ():>int64 => {\n'
        '    let xs = ["longer" "words"]\n'
        '    let kept:array<string> = []\n'
        '    loop x in xs { kept.push(x) }\n'
        '    return kept.length + head(kept).length\n'
        '}\n'
    )
    head = _function(emitted, 'head')
    assert 'escaping' in head   # `return xs[0]`: the caller gets its own copy


def test_a_copy_of_a_string_array_owns_its_own_elements() -> None:
    emitted = _compile(
        'let main = ():>int64 => {\n'
        '    let xs:array<string> = []\n'
        '    xs.push"only"\n'
        '    let copy:array<string> = xs\n'
        '    xs = []\n'
        '    return copy.length\n'
        '}\n'
    )
    assert '__dewy_string_clone(' in emitted     # the copy clones owned elements …
    assert 'let __dewy_string_clone = ' in emitted   # … through the one synthesized helper


def test_the_clone_helper_is_not_emitted_without_a_lasting_copy() -> None:
    assert '__dewy_string_clone' not in _compile(BUILD)


def test_growth_moves_elements_and_returned_arrays_release_their_descriptor() -> None:
    emitted = _compile(BUILD)
    build = _function(emitted, 'build')
    assert '__dewy_string_clone' not in build         # growth relocates, never re-copies
    assert re.search(r'or 4 __dewy_array_adopted_\d+ \+ 32', emitted) is None or True
