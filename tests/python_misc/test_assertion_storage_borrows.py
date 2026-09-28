"""Borrowing separates installed reports from source-message evaluation."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/assertion_storage_borrows.dewy'
CASES = [FIXTURE.read_text(),
    '''Box:type=[values:array<int64>]
read=(snapshot:array<int64> @live:array<int64>):>int64=>{
    live.clear
    return if snapshot.length>?0 snapshot[0] else 1
}
forward=(@box:Box):>int64=>read(box.values @box.values)
main=():>int64=>{let box=Box[[42]] return forward(@box)}''',
    '''Box:type=[values:array<int64> counts:array<int64 length=1>]
change=(@box:Box):>0=>{box.values.clear return 0}
read=(snapshot:array<int64> @count:int64):>int64=>{
    count+=1
    return if snapshot.length>?0 snapshot[0] else 1
}
forward=(@box:Box):>int64=>read(box.values @box.counts[change(@box)])
main=():>int64=>{let box=Box[[42] [0]] return forward(@box)}''',
    # A source helper with a reporting name is still an ordinary call.
    '''let values:array<int64>=[42]
let _assertion_report=(snapshot:array<int64>):>int64=>{
    values.clear
    return if snapshot.length>?0 snapshot[0] else 1
}
forward=(@source:array<int64>):>int64=>_assertion_report(source)
main=():>int64=>forward(@values)''',
]
FAILURE = '''let values:array<int64>=[42]
message=(snapshot:array<int64>):>string=>{
    values.clear
    return if snapshot.length>?0 "saw {snapshot[0]}" else 'lost snapshot'
}
read=(snapshot:array<int64> flag:bool):>int64=>{
    $runtime_assert flag, message(snapshot)
    return 1
}
forward=(@source:array<int64>):>int64=>read(source false)
main=():>int64=>forward(@values)
'''


@pytest.mark.parametrize('source', CASES)
def test_assertion_support_does_not_prevent_storage_borrows(tmp_path, source):
    execute(tmp_path, 'assertion-borrow', codegen(SrcFile(None, source), debug_locations=False))


def test_source_message_still_needs_a_snapshot(tmp_path):
    for result in execute(tmp_path, 'message', codegen(SrcFile(None, FAILURE), debug_locations=False), 101):
        assert 'saw 42' in result.stderr
        assert 'lost snapshot' not in result.stderr


def test_native_assertion_storage_borrows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])


def test_native_source_message_still_needs_a_snapshot(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    path = tmp_path / 'message.dewy'
    path.write_text(FAILURE)
    compiled = subprocess.run([build_program_driver(tmp_path), path, ROOT / 'library', tmp_path / 'prelude'],
                              capture_output=True, text=True, timeout=120)
    assert compiled.returncode == 0, compiled.stderr
    for result in execute(tmp_path, 'native-message', compiled.stdout, 101):
        assert 'saw 42' in result.stderr
        assert 'lost snapshot' not in result.stderr
