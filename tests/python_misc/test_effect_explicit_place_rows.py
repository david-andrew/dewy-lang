"""Generic rows carry nonlocal effects; place permissions remain explicit."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic import effect_rows as rows
from tests.python_misc.test_scalar_projection import execute

FIXTURE=Path(__file__).resolve().parents[1]/'fixtures/effect_explicit_place_rows.dewy'
ERRORS=[
    '''let forward=<E:Effect>(f:(@x:int64):>void & E @y:int64):>void & E=>f(@y)
set=(@x:int64):>void & mutates<x>=>{x=42}
main=():>int64=>{let y:int64=0 forward(@set @y) return y}''',
    '''let forward=<E:Effect>(f:(@x:int64):>void & mutates<x> & E @y:int64 @z:int64):>void & mutates<z> & E=>f(@y)
set=(@x:int64):>void & mutates<x>=>{x=42}
main=():>int64=>{let y:int64=0 let z:int64=0 forward(@set @y @z) return y}''',
]


def test_explicit_place_rows(tmp_path):
    execute(tmp_path, 'explicit-place-rows', codegen(SrcFile.from_path(FIXTURE)))


@pytest.mark.parametrize('source', ERRORS)
def test_place_rows_cannot_be_erased_or_reassigned_by_inference(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_local_exclusions_stay_at_the_callback_boundary():
    place=rows.Atom('reads', rows.Subject('parameter','0'))
    resource=rows.Atom('reads', rows.Subject('resource','Filesystem'))
    formal=rows.Contract(rows.Row(variables=('E',)),(place,))
    actual=rows.Contract(excluded=(place,resource))
    bindings={}
    assert rows.infer(formal,actual,{'E'},bindings)
    assert bindings['E']==rows.Contract(rows.Row(unknown=True),(resource,))


def test_native_explicit_place_rows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=[FIXTURE.read_text()],errors=ERRORS)
