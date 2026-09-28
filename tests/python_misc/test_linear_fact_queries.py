"""Linear queries compose evidence without assuming guards or modular identities."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

BASE = '''check=(a:int64<v=>0<=?v<=?100> b:int64<v=>0<=?v<=?100> c:int64<v=>0<=?v<=?100> d:int64<v=>0<=?v<=?100>):>int64=>{
    if a<=?c and b<=?d { $assert a+b<=?c+d }
    return 42
}
main=():>int64=>check(1 2 3 4)
'''
CASES = [BASE,
    BASE.replace('a+b<=?c+d', 'b+a<=?d+c'),
    BASE.replace('a+b<=?c+d', '2*a+3*b<=?2*c+3*d'),
    BASE.replace('a+b<=?c+d', 'a+b-c<=?d'),
    BASE.replace('a+b<=?c+d', 'a+b-b=?a'),
    BASE.replace('a<=?c and b<=?d', 'a<?c and b<=?d').replace('a+b<=?c+d', 'a+b<?c+d'),
    BASE.replace('a<=?c and b<=?d', 'a<?c and b<=?d').replace('a+b<=?c+d', 'a+b not=?c+d'),
    BASE.replace('a<=?c and b<=?d', 'a=?c and b=?d').replace('a+b<=?c+d', 'a+b=?c+d'),
    BASE.replace('a+b<=?c+d', 'a+b-c-d<=?0'),
    BASE.replace('a+b<=?c+d', 'c+d>=?a+b'),
    BASE.replace('a<=?c and b<=?d', 'a<=?b and b<=?c and c<=?d').replace('a+b<=?c+d', 'a+b<=?c+d'),
    BASE.replace('a+b<=?c+d', 'a+b+7<=?c+d+8'),
]
ERRORS = [
    BASE.replace('a+b<=?c+d', 'a+b>?c+d'),
    BASE.replace('a+b<=?c+d', 'a+b<?c+d'),
    BASE.replace('and b<=?d', ''),
    BASE.replace('$assert', 'c=0\n$assert'),
    BASE.replace('int64<v=>0<=?v<=?100>', 'int8'),
    BASE.replace('a+b<=?c+d', '(a as int8)+(b as int8)<=?(c as int8)+(d as int8)'),
    BASE.replace('a+b<=?c+d', 'a*b<=?c*d'),  # Nonlinear queries are outside this bounded vocabulary.
]

ERRORS += [
    BASE.replace('a+b<=?c+d', '+'.join(['a'] * 65) + '<=?65*c'),
    'opaque=(value:int64<v=>0<=?v<=?100>):>int64<v=>0<=?v<=?100>=>value\n' + BASE.replace('a+b<=?c+d', 'a+b<=?opaque(c)+d'),
]

@pytest.mark.parametrize('source', CASES)
def test_linear_query(tmp_path, source):
    execute(tmp_path, 'linear-query', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_linear_query_needs_exact_current_evidence(source):
    with pytest.raises(ReportException, match='cannot prove|false|outside'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_linear_queries(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
