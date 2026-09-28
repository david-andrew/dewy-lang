"""A dynamic-array call returns an owner that replacement can consume."""
import pytest
from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from test_scalar_projection import execute

PREFIX = '''$explicit_copies
make=(n:int64):>array<string>=>{
    let result:array<string>=[]
    result.push("item {n}")
    return result
}
'''
BODY = '''exercise=():>int64=>{
    let values:array<string>=[]
    values=make(42)
    if values.length not=?1 or values[0] not=?"item 42" return 1
    values=make(1)
    if values.length not=?1 or values[0] not=?"item 1" return 2
    return 42
}
main=():>int64=>{
    if exercise() not=?42 return 1
    let before=_arena_live_bytes
    loop i in [0..40) {if exercise() not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}'''
CASES = [PREFIX+BODY,
    PREFIX+'replace=(@values:array<string> n:int64):>void=>{values=make(n)}\n'+BODY.replace('values=make(42)', 'replace(@values 42)').replace('values=make(1)', 'replace(@values 1)'),
    PREFIX+BODY.replace('values=make(42)', 'loop i in [0..4) {values=make(42)}'),
]

CASES.extend([
    PREFIX+BODY.replace('values=make(42)', 'let next=make(42)\n    values=next'),
    PREFIX+BODY.replace('values=make(42)', 'loop i in [0..4) {let next=make(42) values=next}'),
    PREFIX+BODY.replace('values=make(42)', 'let next=make(1)\n    let before=next.copy()\n    values=next\n    if values.length>?0 {values[0]="item 42"}\n    if before.length not=?1 or before[0] not=?"item 1" return 4'),
])
ERRORS = [PREFIX+BODY.replace('values=make(42)', 'let next=make(42)\n    values=next\n    if next.length=?0 return 4'),
          PREFIX+BODY.replace('values=make(42)', 'let next=make(42)\n    const view=@next\n    values=next\n    if view.length=?0 return 4')]

@pytest.mark.parametrize('source', CASES)
def test_array_result_replacement(tmp_path, source):
    src=SrcFile(None, source)
    emitted=codegen(src, debug_locations=False)
    assert not [note for note in lower.last_copy_notes if note.srcfile==src and note.site.startswith('assigned to')]
    execute(tmp_path, 'array-result-replacement', emitted)


def test_native_array_result_replacement(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


@pytest.mark.parametrize('source', ERRORS)
def test_live_array_or_view_prevents_replacement_move(source):
    from dewy.reporting import ReportException
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)
