"""A bounded call root can lend stable string handles alongside arrays."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute


SOURCE = '''$explicit_copies
Inner:type=[items:array<int64> text:string]
Pair:type=[inner:Inner text:string]
read=(pair:Pair):>int64 & no_effects=>pair.inner.items.length+pair.inner.text.length+pair.text.length
forward=(inner:Inner text:string):>int64 & no_effects=>read(Pair[inner text])
work=(inner:Inner text:string):>int64=>{
    let before:int64=_arena_allocated_bytes
    loop i in 0.. and i<?1000 {if forward(inner text) not=?40 return 1}
    return if _arena_allocated_bytes=?before 42 else 2
}
text=(value:int64):>string=>"{value}"
main=():>int64=>work(Inner[[1 2] text(1234567890123456789)] text(1234567890123456789))
'''
# Two array elements + two nineteen-character decimal strings = forty.
CASES = [SOURCE,
    SOURCE.replace('Pair[inner text]', 'Pair[text=text inner=inner]'),
    SOURCE.replace('Inner:type=[', 'Inner=type of ['),
    SOURCE.replace('items:array<int64> text:string', "items:array<int64> text:'abcdefghijklmnopqrs'|'ABCDEFGHIJKLMNOPQRS'")
          .replace('Pair[inner text]', 'Pair[inner inner.text]')
          .replace('Inner[[1 2] text(1234567890123456789)]', "Inner[[1 2] 'abcdefghijklmnopqrs']"),
    '''Pair:type=[text:string]
read=(pair:Pair):>string=>pair.text
forward=(text:string):>string=>read(Pair[text])
work=(value:int64):>int64=>{
    let text="{value}"
    let kept=forward(text)
    text="changed{value}"
    return if kept=?"{value}" 42 else 1
}
main=():>int64=>{
    if work(42) not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in 0.. and i<?1000 {if work(i) not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}''',
]
ERRORS = [
    SOURCE.replace('pair.inner.items.length+pair.inner.text.length+pair.text.length',
                   '{pair.inner.items.clear return 40}'),
    SOURCE.replace('read=(pair:Pair)', 'read=(pair:Pair ignored:int64)')
          .replace('read(Pair[inner text])', 'read(Pair[inner text] change(@inner))')
          .replace('forward=', 'change=(@inner:Inner):>int64=>{inner.items.clear return 0}\nforward='),
]


@pytest.mark.parametrize('source', CASES)
def test_string_record_argument_loans(tmp_path, source):
    execute(tmp_path, 'string-record-loan', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_string_record_loan_requires_stability(source):
    with pytest.raises(ReportException, match='effect contract|unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_string_record_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
