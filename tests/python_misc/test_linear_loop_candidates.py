"""Linear source queries select finite difference candidates, never evidence."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/linear_loop_candidates.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('2*lower<=?2*upper', '3*lower+2*lower<=?3*upper+2*upper'),
    SOURCE.replace('lower+=1\n        upper+=1',
                   'if lower%2=?0 {lower+=1 upper+=1 continue}\n        lower+=1 upper+=1'),
    SOURCE.replace('loop lower<?10 and upper<?1000', 'loop 2*lower<?2*upper and lower<?10 and upper<?1000'),
]
CASES.append(SOURCE.replace('let lower:int64=0',
    '\n'.join(f'let noise_{i}:int64=0' for i in range(70)) + '\nlet lower:int64=0')
    .replace('lower+=1', '\n'.join(f'noise_{i}+=2' for i in range(70)) + '\nlower+=1'))
CASES.append('''work=(c0:int64<v=>0<=?v<=?100> d0:int64<v=>0<=?v<=?100>):>int64=>{
    let a:int64=0 let b:int64=0 let c:int64=c0 let d:int64=d0
    loop a<?10 and b<?20 and c<?1000 and d<?1000 {
        $assert 2*a+3*b<=?2*c+3*d
        a+=1 c+=1 b+=2 d+=2
    }
    $assert 2*a+3*b<=?2*c+3*d
    return 42
}
main=():>int64=>if work(0 100)=?42 work(100 0) else 1
''')
ERRORS = [
    SOURCE.replace('2*lower<=?2*upper', 'lower*lower<=?upper*upper'),
    SOURCE.replace('upper+=1', 'upper+=0'),
    SOURCE.replace('let lower:int64=0', 'let lower:int64=1'),
    SOURCE.replace('lower+=1\n        upper+=1', 'lower+=1 if lower>?5 continue\n        upper+=1'),
    SOURCE.replace('0<=?v<=?100', '0<=?v<=?int64.max')
          .replace('upper<?1000', 'upper<?int64.max'),
    'change=(@value:int64):>void=>{value=0}\n' + SOURCE.replace('upper+=1', 'change(@upper)'),
]

@pytest.mark.parametrize('source', CASES)
def test_linear_loop_candidates(tmp_path, source):
    execute(tmp_path, 'linear-loop', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_linear_candidate_needs_inductive_evidence(source):
    with pytest.raises(ReportException, match='assertion|cannot prove'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_linear_loop_candidates(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
