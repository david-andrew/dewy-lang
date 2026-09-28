"""Weighted loop facts survive only checked affine updates and valid joins."""
from pathlib import Path
import re

import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/weighted_loop_facts.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('2*i<=?j', 'i*2<=?j'),
    SOURCE.replace('i+=1\n        j+=2',
                   'if i%2=?0 {i+=1 j+=2 continue}\n        i+=1 j+=2'),
    SOURCE.replace('    $assert 2*i<=?j\n    return',
                   '    let saved=i\n    i=200\n    $assert 2*saved<=?j\n    return'),
    '''work=(start:int64<v=>0<=?v<=?100>):>int64=>{
    let i:int64=0 let k:int64=0 let j:int64=start
    loop i<?10 and k<?10 and j<?1000 {
        $assert 2*i+3*k<=?j
        i+=1 k+=1 j+=5
    }
    $assert 3*k+2*i<=?j
    return 42
}
main=():>int64=>work(0)''',
    '''work=():>int64=>{
    let items:array<int64>=[] let i:int64=0
    loop i<?10 {
        $assert 2*i<=?items.length
        i+=1 items.push(1) items.push(2)
    }
    $assert 2*i<=?items.length
    return 42
}
main=():>int64=>work()''',
]
# Routes carry the same weighted evidence as scalar locals.
FIELDS = SOURCE.replace('    let i:int64=0\n    let j:int64=start', '    let counts=Counts[0 start]')
FIELDS = 'Counts:type=[i:int64 j:int64]\n' + re.sub(r'\b(i|j)\b', r'counts.\1', FIELDS)
CASES.append(FIELDS)
ERRORS = [
    FIELDS.replace('counts.j+=2', 'counts.j+=1'),
    '''Counts:type=[i:int64 j:int64]
work=():>int64=>{
    let counts=Counts[120 240]
    loop 0<=?counts.i<=?127 and counts.j<?1000 {
        counts.i=(counts.i as int8)+1
        counts.j+=2
        $assert 2*counts.i=?counts.j
    }
    return 42
}
main=():>int64=>work()''',
    SOURCE.replace('j+=2', 'j+=1'),
    SOURCE.replace('let i:int64=0', 'let i:int64=1'),
    SOURCE.replace('i+=1\n        j+=2', 'i+=1 if i>?5 continue\n        j+=2'),
    SOURCE.replace('    $assert 2*i<=?j\n    return', '    j=0\n    $assert 2*i<=?j\n    return'),
    'change=(@value:int64):>void=>{value=0}\n'+SOURCE.replace('j+=2', 'change(@j)'),
]

@pytest.mark.parametrize('source', CASES)
def test_weighted_loop_facts(tmp_path, source):
    execute(tmp_path, 'weighted-loop', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_weighted_fact_requires_every_edge(source):
    with pytest.raises(ReportException, match='assertion|cannot prove'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_weighted_loop_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
