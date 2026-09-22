"""Local-owner loans must preserve both storage and value snapshots."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/frame_value_storage.dewy').read_text()
CASES = [SOURCE,
    'read=(xs:array<uint8>):>int64=>{if xs.length>?0 return xs[0] as int64 return 0} main=():>int64 & no_effects=>{let xs:array<uint8>=[42] return read(xs)}',
    # The first value must remain a snapshot across later argument effects.
    """Point=type of [x:int64]
read=(point:Point ignored:int64):>int64=>point.x
bump=(@x:int64):>int64=>{x=1 return 0}
main=():>int64=>{let point=Point[42] return read(point bump(@point.x))}""",
    """read=(xs:array<int64> ignored:int64):>int64=>{if xs.length>?0 return xs[0] return 0}
bump=(@x:int64):>int64=>{x=1 return 0}
main=():>int64=>{let xs:array<int64>=[42] return read(xs bump(@xs[0]))}""",
    SOURCE.replace('forward_point(point)', 'forward_point(point=point)').replace('read_array(values)', 'read_array(values=values)'),
]
ERRORS = [
    CASES[2].replace('main=():>int64=>', 'main=():>int64 & no allocates=>'),
    CASES[3].replace('main=():>int64=>', 'main=():>int64 & no allocates=>'),
    """Point=type of [x:int64]
read=(point:Point):>int64=>point.x
main=():>int64 & no allocates=>{let point=Point[42] let alias=point alias.x=1 return read(point)}""",
    """read=(xs:array<int64>):>int64=>{if xs.length>?0 return xs[0] return 0}
main=():>int64 & no allocates=>{let xs:array<int64>=[42] let snapshot=xs return read(snapshot)}""",
    # The local-owner proof must not overlook a capture's possible writes.
    """Point=type of [x:int64]
read=(point:Point ignored:int64):>int64=>point.x
main=():>int64 & no allocates=>{
    let point=Point[42]
    bump=():>int64=>{point.x=1 return 0}
    return read(point bump())
}""",
    # The same storage budget applies to ordinary calls and explicit places.
    'read=(xs:array<int64>):>int64=>xs.length f=():>int64 & no allocates=>{let xs:array<int64>=[' + ' '.join(['42'] * 507) + '] return read(xs)}',
]


@pytest.mark.parametrize('source', CASES)
def test_local_value_loans_execute(source, tmp_path):
    execute(tmp_path, 'frame-values', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', ERRORS)
def test_unknown_local_value_storage_keeps_its_obligation(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_native_frame_value_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
