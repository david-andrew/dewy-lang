"""Objects own their runtime-sized members: scope exit releases them, temporaries move theirs, and field stores release what they replace."""
import re

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def _function(emitted: str, name: str) -> str:
    start = emitted.index(f'let {name} = ')
    end = emitted.find('\nlet ', start)
    return emitted[start:] if end == -1 else emitted[start:end]


POINT = (
    'let Point:type = [name:string tags:array<string> weight:int64|none]\n'
    "let make = (n:int64):>Point => [name='p{n}' tags=['a{n}' \"b\"] weight=n]\n"
)


def test_an_object_local_releases_its_string_and_array_members_at_scope_exit() -> None:
    emitted = _compile(POINT + 'let round = (n:int64):>int64 => {\n    let one = make(n)\n    return one.name.length\n}\nlet main = ():>int64 => round(3)\n')
    body = _function(emitted, 'round')
    # the string field by its owner word, then the tags array's elements, then its buffer
    assert re.search(r'__load_i64__\(__dewy_string_field_string_\d+ \+ 40\) =\? 1', body)
    assert re.search(r'__load_i64__\(__dewy_string_release_element_\d+ \+ 40\)', body)
    assert re.search(r'__load_i64__\(__dewy_string_field_array_\d+ \+ 40\) =\? 1', body)


def test_a_returned_literal_moves_its_array_field_elements_instead_of_cloning() -> None:
    emitted = _compile(POINT + 'let main = ():>int64 => make(3).tags.length\n')
    make = _function(emitted, 'make')
    # the literal's elements change owner as words: no per-element clone of a dying temporary
    assert '__dewy_string_clone(' not in make


def test_a_copied_object_owns_its_copies_and_a_field_store_releases_the_old_string() -> None:
    emitted = _compile(POINT + 'let round = (n:int64):>int64 => {\n    let one = make(n)\n    let two:Point = one\n    two.name = "changed"\n    return two.name.length\n}\nlet main = ():>int64 => round(3)\n')
    body = _function(emitted, 'round')
    # the copy's fields are released too (two owners' worth of field releases) …
    assert len(re.findall(r'let __dewy_string_field_string_\d+:int64', body)) >= 2
    # … and the store over `two.name` gives back the value it held first
    assert re.search(r'let __dewy_string_old_field_\d+:int64 = __load_i64__\(two\)', body)


def test_a_moved_out_array_forgets_its_elements_as_well_as_its_buffer() -> None:
    emitted = _compile('let build = (n:int64):>array<string> => {\n    let parts:array<string> = []\n    loop i in [0..4) { parts.push"{i}-{n}" }\n    return parts\n}\nlet main = ():>int64 => build(3).length\n')
    build = _function(emitted, 'build')
    # the adopt zeroes owner and length, so the scope's element walk has nothing to free
    assert re.search(r'__store_i64__\(0 parts \+ 40\)\n\s*__store_i64__\(0 parts \+ 8\)', build)


def test_stores_through_nested_places_release_the_old_string_and_exact_arrays_release_their_members() -> None:
    emitted = _compile(
        'let Inner:type = [name:string]\n'
        'let Outer:type = [inner:Inner tags:array<string>]\n'
        'let round = (n:int64):>int64 => {\n'
        '    let o:Outer = [inner=[name="a"] tags=["x" "y"]]\n'
        '    o.inner.name = "c{n}"\n'
        '    o.tags[1] = "t{n}"\n'
        '    let xs:array<string> = ["m" "n"]\n'
        '    xs[0] = "e{n}"\n'
        '    let pts:array<[name:string]> = [[name="p"]]\n'
        '    pts[0].name = "q{n}"\n'
        '    return xs[0].length\n'
        '}\n'
        'let main = ():>int64 => round(1)\n'
    )
    body = _function(emitted, 'round')
    assert len(re.findall(r'let __dewy_string_old_field_\d+:int64', body)) == 2      # o.inner.name, pts[0].name
    assert len(re.findall(r'let __dewy_string_old_element_\d+:int64', body)) == 2    # o.tags[1], xs[0]
    # the exact-length arrays' elements are released with them: strings by owner word, the literal's element objects with their block
    assert len(re.findall(r'let __dewy_string_raw_element_\d+:int64', body)) == 3
    assert re.search(r'_arena_release\(__dewy_string_raw_element_\d+ 8\)', body)


def test_a_returned_local_object_hands_its_strings_to_the_result_and_releases_nothing_twice() -> None:
    emitted = _compile(POINT + 'let build = (n:int64):>Point => {\n    let pt = make(n)\n    pt.name = "renamed"\n    return pt\n}\nlet main = ():>int64 => build(3).name.length\n')
    build = _function(emitted, 'build')
    # the adopt moves the name by handle and empties the local's slot …
    assert re.search(r'__store_i64__\(0 pt\)', build)
    # … and the scope release skips an empty slot before reading its owner word
    assert re.search(r'if __dewy_string_field_string_\d+ =\? 0 \{', build)
