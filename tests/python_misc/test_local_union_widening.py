"""Last-use payload transfers survive representation-preserving union widening."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/local_union_widening.dewy').read_text()
TAGGED = '''$explicit_copies
make=(flag:bool):>array<int64>|bool=>if flag [42] else false
widen=(flag:bool):>array<int64>|bool|none=>{let value=make(flag) return value}
main=():>int64=>{
    let value=widen(true)
    if value is? array<int64> and value.length>?0 return value[0]
    return 1
}'''
CASES = [SOURCE, TAGGED,
    SOURCE.replace('return result\n}', 'let widened:Box|int64|none=result\n    return widened\n}'),
    SOURCE.replace('return result\n}', 'if flag return result\n    return none\n}'),
    SOURCE.replace('values.push(widen(flag))', 'let result=make(flag)\n    values.push(result)'),
    SOURCE.replace('values.push(widen(flag))', 'let result=make(flag)\n    values=[result]'),
    SOURCE.replace('$explicit_copies', '').replace('items:array<int64>', 'items:array<int64 length=1>'),
    '''$explicit_copies
Failure=type of []
make=():>bigint=>0x100000000000000000000
widen=(fail:bool):>bigint|Failure=>{let value=make() if fail return Failure[] return value}
main=():>int64=>{let value=widen(false) if value is? Failure return 1 return if value=?0x100000000000000000000 42 else 2}''',
]
RETAINED = '''$explicit_copies
make=():>array<int64>|bool=>[42]
main=():>int64=>{
    let value=make()
    let snapshot=value
    let widened:array<int64>|bool|none=value
    if widened is? array<int64> {widened.clear()}
    if snapshot is? array<int64> and snapshot.length>?0 return snapshot[0]
    return 1
}'''
CASES += [RETAINED.replace('$explicit_copies', ''),
          RETAINED.replace('let snapshot=value', 'let snapshot=value.copy()')]
ERRORS = [RETAINED,
    '''$explicit_copies
widen=(value:array<int64>|bool):>array<int64>|bool|none=>value
main=():>int64=>{
    let original:array<int64>|bool=[42]
    let result=widen(original)
    if result is? array<int64> {result.clear()}
    if original is? array<int64> and original.length>?0 return original[0]
    return 1
}''',
    '''$explicit_copies
make=():>array<int64>|bool=>[42]
main=():>int64=>{
    let value=make()
    let output:array<array<int64>|bool|none>=[]
    loop i in [0..2) {output.push(value)}
    return 42
}''',
]
CASES.append(ERRORS[1].replace('$explicit_copies', ''))

@pytest.mark.parametrize('source', CASES)
def test_local_union_payload_widening(tmp_path, source):
    execute(tmp_path, 'local-union-widening', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_live_union_widening_keeps_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_local_union_payload_widening(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
