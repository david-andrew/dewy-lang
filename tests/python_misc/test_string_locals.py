"""String locals own their values: released at scope exit, moved by `return s`, and every returned string is the caller's."""
import re

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def _function(emitted: str, name: str) -> str:
    start = emitted.index(f'let {name} = ')
    end = emitted.find('\nlet ', start)
    return emitted[start:] if end == -1 else emitted[start:end]


HEAD = (
    'let join2 = (a:string b:string):>string => [a b].join"-"\n'
    'let pick = (text:string flag:bool):>string => if flag text else text.trim\n'
)


def test_an_owning_local_is_released_by_owner_word_at_scope_exit_and_before_reassignment() -> None:
    emitted = _compile(HEAD + 'let round = ():>int64 => {\n    let s:string = join2("a" "b")\n    s = join2(s "x")\n    return s.length\n}\nlet main = ():>int64 => round()\n')
    body = _function(emitted, 'round')
    assert re.search(r'let __dewy_string_assigned_\d+:int64 = join2\(s ', body)   # the new value first …
    assert body.count('if __load_i64__(s + 40) =? 1 {') == 2                      # … then the old one, and again at exit


def test_a_returned_parameter_comes_back_as_a_view_and_a_fresh_result_as_it_is() -> None:
    emitted = _compile(HEAD + 'let main = ():>int64 => pick("ab" true).length\n')
    pick = _function(emitted, 'pick')
    # `return text` (the parameter) is distributed into its arm and wrapped in a view (owner 2) …
    assert re.search(r'__store_i64__\(2 __dewy_string_returned_view_\d+ \+ 40\)', pick)
    # … while `text.trim` (a call) is returned as it is
    assert re.search(r'let __dewy_string_returned_\d+:int64 = \S+string_trim\(text\)\n\s*return __dewy_string_returned_\d+', pick)


def test_return_s_moves_and_a_return_reaching_s_copies() -> None:
    emitted = _compile(HEAD + 'let moved = ():>string => {\n    let s:string = join2("a" "b")\n    return s\n}\nlet copied = ():>string => {\n    let s:string = join2("a" "b")\n    return pick(s true)\n}\nlet main = ():>int64 => moved().length + copied().length\n')
    moved = _function(emitted, 'moved')
    assert 'if __load_i64__(s + 40) =? 1 {' not in moved                 # nothing released: the caller takes it
    copied = _function(emitted, 'copied')
    assert re.search(r'if __load_i64__\(__dewy_string_returned_\d+ \+ 40\) =\? 2 \{', copied)   # a view of `s` is copied
    assert 'if __load_i64__(s + 40) =? 1 {' in copied                     # and `s` released


def test_a_call_result_nothing_keeps_is_a_temporary_released_after_its_statement() -> None:
    emitted = _compile(HEAD + 'let main = ():>int64 => {\n    printl(join2("a" "b"))\n    return 0\n}\n')
    main = _function(emitted, '__dewy_user_main')
    # declared empty at the statement's top, assigned where it arises, released by owner word after
    assigned = re.search(r'(__dewy_string_temp_\d+) = join2\(', main)
    assert assigned, main
    temp = assigned.group(1)
    assert f'let {temp}:int64 = 0' in main
    assert f'if __load_i64__({temp} + 40) =? 1 {{' in main


def test_stack_descriptors_clear_their_owner_word() -> None:
    emitted = _compile('let main = ():>int64 => {\n    let n:int64 = 3\n    let s:string = "{n}!"\n    return s.length\n}\n')
    stack_descriptors = re.findall(r'let (__dewy_string_value_\d+):int64 = __alloca__\(48\)', emitted)
    assert stack_descriptors
    for name in stack_descriptors:
        assert f'__store_i64__(0 {name} + 40)' in emitted


def test_an_array_result_nothing_keeps_is_released_after_its_statement() -> None:
    emitted = _compile('let count = (text:string):>int64 => text.split" ".length\nlet main = ():>int64 => count("a b")\n')
    count = _function(emitted, 'count')
    temp = re.search(r'(__dewy_string_array_temp_\d+) = \S+string_split\(', count)
    assert temp, count
    assert f'let {temp.group(1)}:int64 = 0' in count
    assert re.search(rf'if {temp.group(1)} =\? 0 \{{', count) and re.search(rf'__load_i64__\({temp.group(1)} \+ 40\) =\? 1', count)


def test_an_optional_local_owns_a_calls_string_payload_and_return_moves_it() -> None:
    source = (
        HEAD
        + 'let choose = (flag:bool):>string|none => if flag join2("a" "b") else none\n'
        + 'let moved = ():>string|none => {\n    let maybe:string|none = choose(true)\n    return maybe\n}\n'
        + 'let aliased = ():>string|none => {\n    let maybe:string|none = choose(true)\n    let other:string|none = maybe\n    return other\n}\n'
        + 'let main = ():>int64 => {\n    let m:string|none = moved()\n    match aliased() { s:string => return s.length  <none> => return 0 }\n}\n'
    )
    emitted = _compile(source)
    moved = _function(emitted, 'moved')
    # the payload is released by member tag and owner word …
    assert re.search(r'let __dewy_string_cell_tag_\d+:int64 = __load_i64__\(maybe\)', moved)
    # … except that `return maybe` empties the local's payload word first (the caller owns it now)
    assert '__store_i64__(0 maybe + 8)' in moved
    aliased = _function(emitted, 'aliased')
    # a return reaching `maybe` through `other` clones the payload into the result cell
    assert re.search(r'let __dewy_string_result_tag_\d+:int64', aliased) and re.search(r'let __dewy_string_result_payload_\d+:int64', aliased)
