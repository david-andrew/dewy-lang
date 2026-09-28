"""Join borrows its input until a later separator expression can change it."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

READ_ONLY = '''$explicit_copies
join=(parts:array<string>):>string=>parts.join('/')
main=():>int64=>{
    let parts:array<string>=['a' 'b']
    return if join(parts)=?'a/b' and parts.length=?2 42 else 1
}'''
SNAPSHOT = '''separator=(@items:array<string>):>string=>{
    items.clear items.push('new') return '-'
}
main=():>int64=>{
    let items:array<string>=['a' 'b']
    let result=items.join(separator(@items))
    return if result=?'a-b' and items.length=?1 and items[0]=?'new' 42 else 1
}'''
CASES = [READ_ONLY, SNAPSHOT,
    SNAPSHOT.replace('items.join(separator(@items))', 'items.join(sep=separator(@items))'),
    '''let items:array<string>=['a' 'b']
separator=():>string=>{items.clear items.push('new') return '-'}
join=(@source:array<string>):>string=>source.join(separator())
main=():>int64=>if join(@items)=?'a-b' 42 else 1''',
    '''separator=(@items:array<string>):>string=>{items.clear return '-'}
join=(@source:array<string> @alias:array<string>):>string=>source.join(separator(@alias))
main=():>int64=>{
    let items:array<string>=['a' 'b']
    let other:array<string>=['c']
    return if join(@items @other)=?'a-b' and other.length=?0 42 else 1
}''',
    '''make=():>array<string>=>['a' 'b']
exercise=():>int64=>{
    let first=make().join('-')
    let second=['a' 'b'].join('-')
    return if first=?'a-b' and second=?'a-b' 42 else 1
}
main=():>int64=>{
    if exercise() not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in [0..100) {if exercise() not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}''',
]
CASES.append((Path(__file__).resolve().parents[1] / 'fixtures/array_join_snapshots.dewy').read_text())
ERRORS = ['''$explicit_copies
separator=(@items:array<string>):>string=>{items.clear return '-'}
join=(@items:array<string>):>string=>items.join(separator(@items))
main=():>int64=>{
    let items:array<string>=['a' 'b']
    return if join(@items)=?'a-b' 42 else 1
}''']


@pytest.mark.parametrize('source', CASES)
def test_join_receiver_lifetime(tmp_path, source):
    execute(tmp_path, 'join', codegen(SrcFile(None, source), debug_locations=False))


def test_join_snapshot_obeys_copy_policy():
    with pytest.raises(ReportException, match='separator expression may write'):
        codegen(SrcFile(None, ERRORS[0]), debug_locations=False)


def test_native_join_receiver_lifetime(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
