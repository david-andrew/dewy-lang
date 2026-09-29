"""Replacing a tagged owner consumes last-use payloads, including widening."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute


SOURCE = '''$explicit_copies
make=(present:bool):>array<int64>|bool=>if present [20 22] else false
work=(present:bool):>int64=>{
    let value=make(present)
    let result:array<int64>|bool|none=none
    result=value
    if result is? none return 1
    if result is? bool return if not result 42 else 2
    return if result.length=?2 result[0]+result[1] else 3
}
main=():>int64=>{
    if work(true) not=?42 or work(false) not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in [0..1000) {if work(true) not=?42 or work(false) not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}
'''
CASES = [SOURCE,
    SOURCE.replace('array<int64>|bool|none=none', 'array<int64>|bool=false')
          .replace('    if result is? none return 1\n', ''),
    SOURCE.replace('result=value', 'if present {result=value} else {result=false}'),
    SOURCE.replace('array<int64>|bool', 'Payload|bool')
          .replace('make=', 'Payload:type=[items:array<int64>]\nmake=', 1)
          .replace('if present [20 22]', 'if present Payload[[20 22]]')
          .replace('result.length', 'result.items.length')
          .replace('result[0]+result[1]', 'result.items[0]+result.items[1]'),
    SOURCE.replace('make=(present:bool):>array<int64>|bool=>if present [20 22] else false',
                   'make=(present:bool):>bigint=>if present 42 else 42')
          .replace('let result:array<int64>|bool|none=none', 'let result:bigint?=none')
          .replace('    if result is? bool return if not result 42 else 2\n', '')
          .replace('return if result.length=?2 result[0]+result[1] else 3',
                   'return if result=?42 42 else 3'),
]
ERRORS = [SOURCE.replace('result=value',
                         'result=value\n    if value is? bool return 42'),
          SOURCE.replace('let value=make(present)',
                         'let values=[make(present)]\n    const value=@values[0]')]


@pytest.mark.parametrize('source', CASES)
def test_union_replacement_moves(tmp_path, source):
    execute(tmp_path, 'union-replacement', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_union_replacement_requires_an_owned_last_use(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_union_replacement_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
