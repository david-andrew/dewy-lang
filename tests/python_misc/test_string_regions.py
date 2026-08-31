"""Frame regions: string storage no `return` reaches comes from the function's region; returned strings stay in the arena."""
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile


def _body(source: str, name: str) -> str:
    emitted = codegen(SrcFile(None, source))
    start = emitted.index(f'let {name} =')
    end = emitted.find('\nlet ', start + 1)
    return emitted[start:end if end > 0 else None]


def test_frame_only_views_use_the_region_and_release_it_at_exit() -> None:
    body = _body('let count = (text:string):>int64 => { if text.length >? 0 { let head:string = text[0..0]  return head.length + text.length }  return 0 }\nlet main = ():>int64 => count("ab")\n', 'count')
    assert '_region_new()' in body and '_region_alloc(' in body and '_region_release(' in body
    assert '_arena_alloc(' not in body
    assert body.index('_region_release(') < body.rindex('return')


def test_returned_views_stay_in_the_arena() -> None:
    body = _body('let head = (text:string):>string => { if text.length >? 0 { return text[0..0] }  return text }\nlet main = ():>int64 => head("ab").length\n', 'head')
    assert '_arena_alloc(' in body and '_region_alloc(' not in body


def test_a_returned_local_view_keeps_its_source_out_of_the_region() -> None:
    body = _body(
        'let tail = (bytes:array<uint8>):>string => { match bytes as string|none { s:string => return s  <none> => return "" } }\n'
        'let main = ():>int64 => tail([104 105]).length\n', 'tail')
    assert '_region_alloc(' not in body   # the decoded string is returned: arena


def test_functions_without_frame_strings_get_no_region() -> None:
    body = _body('let add = (a:int64 b:int64):>int64 => a + b\nlet main = ():>int64 => add(40 2)\n', 'add')
    assert '_region' not in body
