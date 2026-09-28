"""Const module storage can lend values, unless its address was exposed."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/constant_global_views.dewy'
EXPOSED = '''const values:array<array<int64>>=[[42]]
let pointer=__load_i64__(__load_i64__(__load_i64__(values transmute int64)))
change=():>void=>{__store_i64__(99 pointer)}
main=():>int64=>{
    $runtime_assert values.length>?0
    const snapshot=values[0]
    change()
    return if snapshot.length>?0 snapshot[0] else 1
}'''


@pytest.mark.parametrize('source', [FIXTURE.read_text(), EXPOSED])
def test_constant_globals_keep_value_semantics(tmp_path, source):
    execute(tmp_path, 'constant-global', codegen(SrcFile(None, source), debug_locations=False))


def test_exposed_constant_global_cannot_supply_required_view():
    with pytest.raises(ReportException, match='required local view'):
        codegen(SrcFile(None, EXPOSED.replace('snapshot=values', 'snapshot=@values')))


def test_native_constant_global_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[FIXTURE.read_text(), EXPOSED],
                          errors=[EXPOSED.replace('snapshot=values', 'snapshot=@values')])
