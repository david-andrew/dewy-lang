"""Integer snapshots retain equality only while both endpoints are unchanged."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

CASES = [
    'check=(value:int64):>int64=>{const saved=value $assert saved=?value return saved} main=():>int64=>check(42)',
    'check=(value:int64):>int64=>{let saved=value $assert saved=?value return saved} main=():>int64=>check(42)',
    'Box:type=[value:int64] check=(@box:Box):>int64=>{const saved=box.value $assert saved=?box.value return saved} main=():>int64=>{let box:Box=[42] return check(@box)}',
    'check=(value:int64<v=>0<=?v<?100>):>int64=>{if value>=?99 return value const saved=value value+=1 $assert saved<?value return saved} main=():>int64=>check(42)',
]
ERRORS = [
    'check=(value:int64<v=>v>=?0>):>void=>{value=-1}',
    'check=(value:int64<v=>0<=?v<?100>):>void=>{value=100 $assert value<?100}',
    'check=(@value:int64<v=>0<=?v<?100>):>void=>{value+=1}', 
    'check=(value:int64):>void=>{const saved=value value=0 $assert saved=?value}',
    'check=(value:int64):>void=>{let saved=value saved=0 $assert saved=?value}',
    'clear=(@value:int64):>void=>{value=0} check=(value:int64):>void=>{const saved=value clear(@value) $assert saved=?value}',
    'Box:type=[value:int64] check=(@box:Box):>void=>{const saved=box.value box.value=0 $assert saved=?box.value}',
    'check=(value:int64):>void=>{let saved:int64=0 loop i in 0..2 {if i=?0 {saved=value} else {value=0} $assert saved=?value}}',
]

@pytest.mark.parametrize('source', CASES)
def test_scalar_snapshot_equality(tmp_path, source):
    execute(tmp_path, 'scalar-snapshot', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_scalar_snapshot_invalidation(source):
    with pytest.raises(ReportException, match='cannot prove|false|refinement'):
        codegen(SrcFile(None, source))


def test_native_scalar_snapshot_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
