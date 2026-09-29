"""A child payload can move to a parent result while keeping its full value."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
TransferBase=type of [values:array<int64>]
TransferChild=type of TransferBase & [extra:string='child' more:array<int64>=[42]]
TransferWide=type of TransferBase & [one:string two:string three:array<int64> four:int64?]
TransferOther:type=[other:array<int64>]
make=(yes:bool):>TransferChild|TransferOther=>{
 let values:array<int64>=[]
 values.reserve(1025)
 loop i in [0..1024) {values.push(i)}
 return if yes TransferChild[values] else TransferOther[values]
}
forward=(yes:bool):>TransferBase|bool=>{
 let parsed=make(yes)
 if parsed is? TransferBase return parsed
 return false
}
work=():>int64=>{
 let value=forward(true)
 if value is? TransferChild {
  value.values.push(42)
  value.more.push(7)
  return if value.values.length=?1025 and value.values[1024]=?42 and value.extra=?'child' and value.more.length=?2 and value.more[0]=?42 42 else 1
 }
 return 2
}
main=():>int64=>{
 if work() not=?42 return 3
 let before:int64=_arena_live_bytes
 loop i in [0..20) {if work() not=?42 return 4}
 return if _arena_live_bytes=?before 42 else 5
}
'''
CASES = [SOURCE,
    SOURCE.replace('if parsed is? TransferBase return parsed', 'if parsed is? TransferBase {let result:TransferBase|bool=parsed return result}'),
    SOURCE.replace('make=(yes:bool):>TransferChild|TransferOther', 'make=(yes:bool):>TransferChild').replace(
        'return if yes TransferChild[values] else TransferOther[values]', 'return TransferChild[values]'),
]
ERROR = SOURCE.replace('if parsed is? TransferBase return parsed',
    'if parsed is? TransferBase {let result:TransferBase|bool=parsed parsed.values.push(7) return result}')

@pytest.mark.parametrize('source', CASES)
def test_nominal_payload_transfer(tmp_path, source):
    execute(tmp_path, 'nominal-payload-transfer', codegen(SrcFile(None, source), debug_locations=False))


def test_nominal_payload_retained_reader_rejects():
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, ERROR), debug_locations=False)


def test_native_nominal_payload_transfer(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[ERROR])


def test_bootstrap_test_syntax_uses_checked_transfers(tmp_path):
    from dewy.backend.udewy import lower
    source = Path(__file__).resolve().parents[1] / 'fixtures/strict_test_syntax.dewy'
    generated = codegen(SrcFile.from_path(source), debug_locations=False)
    assert not [note for note in lower.last_copy_notes
                if note.srcfile.path and note.srcfile.path.name == 'test_syntax.dewy'
                and note.runtime_sized and not note.explicit and not note.policy_exempt]
    execute(tmp_path, 'strict-test-syntax', generated)
