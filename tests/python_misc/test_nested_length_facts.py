"""Common element lengths are facts about the current container contents."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

CASES = [
    'main=():>int64=>{let xs:array<array<int64>>=[[42] [7 8]] return xs[0][0]}',
    'main=():>int64=>{let xs:array<array<int64>>=[] xs.push([42]) xs.insert([42 9] 0) return xs[0][0]}',
    'main=():>int64=>{let xs:array<array<int64>>=[[42]] let ys=xs xs[0].clear return ys[0][0]}',
    'make=():>array<array<int64> length=1>=>[[42]]\nmain=():>int64=>{let xs=make() if xs[0].length=?1 return xs[0][0] return 0}',
    'make=():>array<string length=1>=>["local"]\nmain=():>int64=>{let xs=make() return if xs[0]=?"local" 42 else 0}',
]
ERRORS = [
    'main=():>int64=>{let xs:array<array<int64>>=[[42]] xs[0].clear return xs[0][0]}',
    'main=():>int64=>{let xs:array<array<int64>>=[[42]] xs[0]=[] return xs[0][0]}',
    'clear=(@xs:array<int64>):>void=>xs.clear\nmain=():>int64=>{let xs:array<array<int64>>=[[42]] clear(@xs[0]) return xs[0][0]}',
    'main=():>int64=>{let xs:array<array<int64>>=[[42]] xs.push([]) return xs[1][0]}',
    'main=():>int64=>{let xs:array<array<int64>>=[[42]] let empty:array<int64>=[] xs.insert(empty 0) return xs[0][0]}',
]

@pytest.mark.parametrize('source', CASES)
def test_common_lengths(tmp_path, source):
    execute(tmp_path, 'nested-lengths', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_mutation_invalidates_common_lengths(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_nested_lengths(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
