"""Empty paths contribute vacuous element evidence, never replacement evidence."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic.check import typecheck_and_resolve
from test_scalar_projection import execute

BASE = '''probe=(a:int64 b:int64 choose:bool):>int64=>{
    if a<=?b return 0
    let values:array<int64>=[]
    if choose {values.push(a)}
    if values.length=?0 return 42
    let saved=values[0]
    $assert saved>?b
    return 42
}
main=():>int64=>probe(8 4 true)'''
CASES = [BASE, BASE.replace('true)', 'false)'),
    BASE.replace('if a<=?b', 'if a=?b').replace('saved>?b', 'saved not=?b'),
    BASE.replace('if a<=?b', 'if a<?1 or a>?10').replace('saved>?b', '1<=?saved<=?10'),
    BASE.replace('if a<=?b', 'if a=?0').replace('saved>?b', 'saved not=?0'),
    BASE.replace('if choose {values.push(a)}', 'loop i in [0..3) {values.push(a)}'),
]
ERRORS = [BASE.replace('if choose {values.push(a)}', 'if choose {values.push(a)} else {values.push(b)}'),
    BASE.replace('if choose {values.push(a)}', 'if choose {values.push(a)}\n    values.clear\n    values.push(b)')]


@pytest.mark.parametrize('source', CASES)
def test_empty_element_join(tmp_path, source):
    execute(tmp_path, 'empty-element-join', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_nonempty_paths_need_the_same_fact(source):
    with pytest.raises(ReportException):
        typecheck_and_resolve(SrcFile(None, source))

def test_native_empty_element_joins(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
