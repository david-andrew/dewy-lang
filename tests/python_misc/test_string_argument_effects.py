"""Passing a string is no allocation; storing one still is.

Strings are immutable shares: neither compiler copies a string at a call,
only where it is stored (row S5's largest shortcut class). Allocation
contracts therefore count no storage for a string argument, while a callee
that stores its string parameter counts the store in its own body.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PASSED = '''size = (text:string):>int64 & no allocates => 21
pick = (x:int64):>int64 & no allocates => size(if x >? 0 'yes' else 'no') + size('lit') - 21
forward = (text:string):>int64 & no allocates => size(text)
main = ():>int64 => {
    let t="forty-{2}"
    return pick(1) + forward(t)
}
'''
STORED = '''Box:type=[name:string]
rename = (@b:Box text:string):>void & no allocates => {b.name=text}
main = ():>int64 => {
    let b=Box['x']
    rename(@b 'forty-two')
    return 42
}
'''
CASES = [PASSED]
ERRORS = [STORED]


@pytest.mark.parametrize('source', CASES)
def test_string_arguments_do_not_allocate(tmp_path, source):
    execute(tmp_path, 'string-arguments', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_stored_string_parameter_allocates(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_string_argument_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
