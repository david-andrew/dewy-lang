"""Inductive differences may start from bounded intervals, not just constants."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PAIR = '''work=(start:int64<v=>0<=?v<=?100>):>int64=>{
    let lower:int64=0 let upper:int64=start
    loop lower<?10 and upper<?int64.max {
        $assert lower<=?upper
        lower+=1 upper+=1
    }
    $assert lower<=?upper
    $assert upper-lower<=?100
    return 42
}
main=():>int64=>if work(0)=?42 and work(100)=?42 42 else 1'''
CASES = [
    PAIR,
    PAIR.replace('lower+=1 upper+=1', 'if lower%2=?0 {lower+=1 upper+=1 continue}\nlower+=1 upper+=1'),
    PAIR.replace('let lower:int64=0 let upper:int64=start', 'let unrelated:int64=0 let lower:int64=0 let upper:int64=start').replace('lower+=1 upper+=1', 'unrelated+=2 lower+=1 upper+=1'),
]
ERRORS = [
    PAIR.replace('upper+=1', 'upper+=2'),  # breaks the upper difference bound
    PAIR.replace('lower+=1 upper+=1', 'lower+=1 if lower>?5 continue\nupper+=1'),
    PAIR.replace('let lower:int64=0', 'let lower:int64=1'),  # not established at entry
    'change=(@value:int64):>void=>{value=0}\n'+PAIR.replace('upper+=1', 'change(@upper)'),
]


@pytest.mark.parametrize('source', CASES)
def test_interval_difference_is_inductive(tmp_path, source):
    execute(tmp_path, 'interval-qualifier', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_interval_qualifiers_check_every_edge(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_interval_loop_qualifiers(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
