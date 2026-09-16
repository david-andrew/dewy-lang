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
    release = re.search(r'(__dewy_release_object_\d+)\(one\)', body)
    assert release is not None
    body = _function(emitted, release[1])
    # The shared helpers release the string and the array's elements/buffer.
    # Ownership checks live in those helpers rather than at every field site.
    assert re.search(r'__dewy_release_string\(__dewy_string_field_string_\d+\)', body)
    array_release = re.search(r'(__dewy_release_array_\d+)\(__dewy_string_field_array_\d+\)', body)
    assert array_release is not None
    array_body = _function(emitted, array_release[1])
    assert re.search(r'__dewy_release_string\(__dewy_string_release_element_\d+\)', array_body)
    assert '_arena_release(' in array_body


def test_a_returned_literal_moves_its_array_field_elements_instead_of_cloning() -> None:
    emitted = _compile(POINT + 'let main = ():>int64 => make(3).tags.length\n')
    make = _function(emitted, 'make')
    # Materializing the interpolated strings may copy frame storage. The
    # later element-transfer loop must move those handles without cloning.
    transfer = re.search(r'loop __dewy_array_copy_index_\d+ .*?\n    \}', make, re.S)
    assert transfer is not None
    assert '__store_i64__(__load_i64__(' in transfer[0]
    assert '__dewy_string_clone(' not in transfer[0]
    assert re.search(r'__store_i64__\(0 __dewy_array_shared_source_\d+ \+ 8\)', make)


def test_a_copied_object_owns_its_copies_and_a_field_store_releases_the_old_string() -> None:
    emitted = _compile(POINT + 'let round = (n:int64):>int64 => {\n    let one = make(n)\n    let two:Point = one\n    two.name = "changed"\n    return two.name.length\n}\nlet main = ():>int64 => round(3)\n')
    body = _function(emitted, 'round')
    # the copy's fields are released too (two owners' worth of field releases) …
    assert re.search(r'__dewy_release_object_\d+\(two\)', body)
    assert re.search(r'__dewy_release_object_\d+\(one\)', body)
    # … and the store over `two.name` gives back the value it held first
    assert re.search(r'let __dewy_string_previous_field_\d+:int64 = __load_i64__\(two\)', body)


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
    assert len(re.findall(r'let __dewy_string_previous_field_\d+:int64', body)) == 2      # o.inner.name, pts[0].name
    assert len(re.findall(r'let __dewy_string_old_element_\d+:int64', body)) == 2    # o.tags[1], xs[0]
    # the exact-length arrays' elements are released with them: strings by owner word, the literal's element objects with their block
    assert len(re.findall(r'let __dewy_string_raw_element_\d+:int64', body)) == 3
    assert re.search(r'_arena_release(_8\(__dewy_string_raw_element_\d+|\(__dewy_string_raw_element_\d+ 8)\)', body)


def test_a_returned_local_object_hands_its_strings_to_the_result_and_releases_nothing_twice() -> None:
    emitted = _compile(POINT + 'let build = (n:int64):>Point => {\n    let pt = make(n)\n    pt.name = "renamed"\n    return pt\n}\nlet main = ():>int64 => build(3).name.length\n')
    build = _function(emitted, 'build')
    # the adopt moves the name by handle and empties the local's slot …
    copied = re.search(r'(__dewy_copy_object_\d+)\(__dewy_result_\d+ pt\)', build)
    assert copied is not None
    assert re.search(r'__store_i64__\(0 __dewy_src\)', _function(emitted, copied[1]))
    # … and the shared string release skips an empty slot before its owner read.
    released = re.search(r'(__dewy_release_object_\d+)\(pt\)', build)
    assert released is not None
    assert re.search(r'__dewy_release_string\(__dewy_string_field_string_\d+\)', _function(emitted, released[1]))
    string_release = _function(emitted, '__dewy_release_string')
    assert string_release.index('if __dewy_value =? 0') < string_release.index('__dewy_value + 40')
