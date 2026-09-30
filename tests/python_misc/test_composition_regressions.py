"""Parsed directives and resolved bindings decide behavior, not spelling, and
rewrites keep evaluation order (September 29 audit follow-up, item 1)."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

SHIFT = '''shift=(x:uint64 n:uint64):>uint64=>x << n
main=():>int64=>if (shift(1 64) transmute int64) =? 1 42 else 0
'''
CASES = [
    # The directive means the same with a comment between its parts.
    '$no_prelude = true\n' + SHIFT,
    '$no_prelude = # comment\ntrue\n' + SHIFT,
    # A user `printl` receives the interpolated call; nothing is printed.
    '''let count:int64=0
let printl=<T>(x:T):>void=>{count+=1}
main=():>int64=>{printl"A{2}B" return if count =? 1 42 else 0}''',
    # A shadowing `print` does not capture the prelude `printl`'s parts.
    '''let count:int64=0
let print=<T>(x:T):>void=>{count+=1}
main=():>int64=>{printl"A{2}B" return if count =? 0 42 else 0}''',
    # Streaming writes nothing before every field has been evaluated.
    '''side=():>int64=>{printl"SIDE" return 2}
main=():>int64=>{printl"A{side()}B" return 42}''',
    '''side=():>int64=>{printl"SIDE" return 2}
main=():>int64=>{let s="A{side()}B" printl(s) return 42}''',
]
OUTPUTS = ['', '', '', 'A2B\n', 'SIDE\nA2B\n', 'SIDE\nA2B\n']


@pytest.mark.parametrize('index', range(len(CASES)))
def test_composition_regression(tmp_path, index):
    results = execute(tmp_path, 'composition', codegen(SrcFile(None, CASES[index]), debug_locations=False))
    assert all(result.stdout == OUTPUTS[index] for result in results)


def test_native_composition_regressions(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[], outputs=OUTPUTS)
