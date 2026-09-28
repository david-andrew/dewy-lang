"""Copy/move hooks alone do not require complete wrappers during cleanup."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

HEADER = '''let trace:int64=0
let hook_calls:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
Wrapper=type of [first:Token second:Token
$__copy__ duplicate=():>Wrapper=>{hook_calls+=1 return Wrapper[Token[8] Token[9]]}
$__move__ relocate=():>Wrapper=>{hook_calls+=1 return Wrapper[Token[8] Token[9]]}
]
consume=(value:Token):>int64=>value.id
'''
CASES = [
    HEADER + '''work=():>int64=>{
    let owner=Wrapper[Token[1] Token[2]]
    let first=owner.first
    return if first.id=?1 and owner.second.id=?2 42 else 1
}
main=():>int64=>{let answer=work() return if trace=?12 and hook_calls=?0 answer else 2}''',
    HEADER + '''take=():>Token=>{
    let owner=Wrapper[Token[1] Token[2]]
    return owner.first
}
work=():>int64=>{
    let first=take()
    return if first.id=?1 and trace=?2 42 else 1
}
main=():>int64=>{let answer=work() return if trace=?21 and hook_calls=?0 answer else 2}''',
    HEADER + '''work=(flag:bool):>int64=>{
    let owner=Wrapper[Token[1] Token[2]]
    if flag {consume(owner.first);}
    return owner.second.id
}
main=():>int64=>{
    if work(true) not=?2 or trace not=?12 or hook_calls not=?0 return 1
    trace=0
    return if work(false)=?2 and trace=?21 and hook_calls=?0 42 else 2
}''',
    HEADER + '''work=(flag:bool):>int64=>{
    let owner=Wrapper[Token[1] Token[2]]
    if flag {consume(owner.first);}
    owner.first=Token[3]
    return owner.first.id
}
main=():>int64=>{
    if work(true) not=?3 or trace not=?123 or hook_calls not=?0 return 1
    trace=0
    return if work(false)=?3 and trace=?123 and hook_calls=?0 42 else 2
}''',
]
for hook in ['duplicate', 'relocate']:
    CASES.append('\n'.join(line for line in CASES[2].splitlines()
                           if f'{hook}=' not in line))
CASES.append((Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_partial_hook_wrappers.dewy').read_text())
ERRORS = [HEADER + '''work=(flag:bool):>int64=>{
    let owner=Wrapper[Token[1] Token[2]]
    if flag {consume(owner.first);}
    return owner.first.id
}''',
    HEADER.replace('Wrapper=type of [first:Token second:Token',
                   'Wrapper=type of [first:Token second:Token\n$__drop__ release=():>void=>{trace=first.id}') +
    '''take=():>Token=>{let owner=Wrapper[Token[1] Token[2]] return owner.first}''']


@pytest.mark.parametrize('source', CASES)
def test_partial_wrapper_cleanup(tmp_path, source):
    execute(tmp_path, 'partial-hook-wrapper', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_partial_wrapper_still_needs_valid_reads(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_partial_wrapper_cleanup(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
