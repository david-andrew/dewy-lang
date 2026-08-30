"""The placement step for strings: an escape copy only when the string may be frame-backed (or a parameter's)."""
from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile


def _copies(source: str) -> list[str]:
    codegen(SrcFile(None, source))
    return [note.message for note in lower.last_copy_notes]


def test_static_and_arena_strings_are_stored_without_copies() -> None:
    copies = _copies(
        'let collect = (names:array<string> bytes:array<uint8>):>array<string> => {\n'
        '    let found:array<string> = []\n'
        '    found.push("literal")\n'
        '    loop name in names { found.push(name) }\n'                    # an element: arena-backed
        '    found.push(["a" "b"].join)\n'                                 # a join: a frame-region string, copied when stored
        '    match bytes as string|undefined { s:string => found.push(s)  <undefined> => {} }\n'   # a decode: frame region, copied when stored
        '    let stem:string = "x.dewy"\n'
        '    found.push(stem[0..0])\n'                                     # a view into a static string
        '    return found\n'
        '}\n'
        'let main = ():>int64 => collect(["p"] [104]).length\n'
    )
    # the join and the decoded string live in the frame region (no return reaches them): stored, they are copied
    assert len(copies) == 3   # the join, the decoded string, and the element of `names`
    assert sum('current frame' in message for message in copies) == 2 and sum('owned by the container' in message for message in copies) == 1


def test_frame_and_caller_strings_are_copied_and_reported() -> None:
    copies = _copies(
        'let label = (prefix:string i:int64):>string => "{prefix}-{i}"\n'
        'let collect = (dir:string):>array<string> => {\n'
        '    let found:array<string> = []\n'
        '    found.push("{dir}/x")\n'                    # an interpolation: frame
        '    found.push(label(dir 1))\n'                 # a call result: frame
        '    found.push(dir)\n'                          # a parameter: the caller\'s
        '    let piece:string = "{dir}!"\n'
        '    if piece.length >? 0 { found.push(piece[0..0]) }\n'                  # a view into a frame string
        '    return found\n'
        '}\n'
        'let main = ():>int64 => collect("d").length\n'
    )
    assert len(copies) == 4
    assert sum('current frame' in message for message in copies) == 3
    assert sum('parameter' in message for message in copies) == 1


def test_object_fields_follow_the_same_rule() -> None:
    copies = _copies(
        'let Named:type = [path:string]\n'
        'let make = (a:string):>Named => [path = "{a}/b"]\n'
        'let keep = (a:string):>Named => [path = "fixed"]\n'
        'let main = ():>int64 => make("x").path.length + keep("y").path.length\n'
    )
    assert len(copies) == 1 and 'current frame' in copies[0]
