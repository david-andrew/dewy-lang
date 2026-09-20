"""The placement step for strings: an escape copy only when the string may be frame-backed (or a parameter's)."""
from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile


def _copies(source: str) -> list[str]:
    codegen(SrcFile(None, source))
    return [note.message for note in lower.last_copy_notes if note.kind == 'string']


def test_static_literals_are_shared_but_temporary_views_and_owned_elements_are_copied() -> None:
    copies = _copies(
        'let collect = (names:array<string> bytes:array<uint8>):>array<string> => {\n'
        '    let found:array<string> = []\n'
        '    found.push("literal")\n'
        '    loop name in names { found.push(name) }\n'                    # an element: arena-backed
        '    found.push(["a" "b"].join)\n'                                 # a join: a frame-region string, copied when stored
        '    match bytes as string|none { s:string => found.push(s)  <none> => {} }\n'   # a decode: frame region, copied when stored
        '    let stem:string = "x.dewy"\n'
        '    found.push(stem[0..0])\n'                                     # a view into a static string
        '    return found\n'
        '}\n'
        'let main = ():>int64 => collect(["p"] [104]).length\n'
    )
    # A narrowed match payload is borrowed from its optional cell: retaining
    # it as `s` and then storing it in `found` gives each owner its own copy.
    assert len(copies) == 5   # join, retained decode, stored decode, slice, names element
    assert sum('current frame' in message for message in copies) == 2
    assert sum('owned by the container' in message for message in copies) == 3


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


def test_copy_report_names_kind_site_and_reason(tmp_path):
    """`dewy analyze` lists every record and array copy with a site and a reason.

    The native compiler prints the same `copy:` lines (see
    tests/python_misc/test_bootstrap_compiler_command.py).
    """
    from pathlib import Path
    srcfile = SrcFile.from_path(Path(__file__).resolve().parents[2] / 'dewy/tests/copy_report.dewy')
    codegen(srcfile, target='x86_64')
    lines = [note.line for note in lower.last_copy_notes]
    # `let f = facts[id]` borrows the dictionary's storage; the copy is at the return
    assert any(line.startswith('record `Fact` copied when returned') for line in lines)
    assert not any('bound to `f`' in line for line in lines)
    assert any('bound to `h`: `g` may be used again' in line for line in lines)
    assert any(line.startswith('string copied when stored') for line in lines)
    kinds = {note.kind for note in lower.last_copy_notes}
    assert kinds >= {'record', 'string'}


def test_union_snapshots_and_retagging_are_in_the_inventory():
    from pathlib import Path
    source = SrcFile.from_path(Path(__file__).resolve().parents[1] / 'fixtures/copy_report_coverage.dewy')
    codegen(source)
    notes = [note for note in lower.last_copy_notes if note.srcfile.path == source.path]
    assert any(note.kind == 'cell' and note.site == 'stored in a union' for note in notes)
    assert any(note.kind == 'cell' and note.site == 'converted to a union' for note in notes)
    assert any(note.kind == 'string' for note in notes)
    assert all(note.message and not note.explicit for note in notes)


def test_explicit_union_copy_is_not_reported_again_as_implicit():
    codegen(SrcFile(None, 'Box:type=[value:int64]\nf=(value:Box|none):>Box|none=>value.copy()\nmain=():>int64=>{let value=f(Box[42]) if value is? Box return value.value return 0}'))
    explicit = [note for note in lower.last_copy_notes if note.explicit]
    assert len(explicit) == 1 and explicit[0].kind == 'cell'
    assert not any(note.loc == explicit[0].loc and not note.explicit for note in lower.last_copy_notes)
