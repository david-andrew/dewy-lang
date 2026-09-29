"""A private input can become a local owner after checked read-only calls."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute
from test_observed_consuming_inputs import SOURCE, OPTIONAL

ALIAS=SOURCE.replace('return value\n}', 'let owned=value\n owned.values.push(0)\n owned.values.pop;\n return owned\n}')
OBSERVER=SOURCE.replace('keep=(value:Item)', 'size=(item:Item):>addr=>item.size\nkeep=(value:Item)').replace('if value.size=?0', 'if size(value)=?0')
CASES=[ALIAS,OBSERVER,ALIAS.replace('if value.size=?0', 'if size(value)=?0').replace('keep=(value:Item)', 'size=(item:Item):>addr=>item.size\nkeep=(value:Item)'),
 OPTIONAL.replace('out.push(value)', 'let owned=value\n owned.values.push(0)\n owned.values.pop;\n out.push(owned)'),
 '''$explicit_copies
Fraction:type=const [numerator:bigint denominator:bigint & ~0]
fraction=(numerator:bigint denominator:bigint):>Fraction=>{
 $runtime_assert denominator isnt? 0
 return Fraction[numerator denominator]
}
main=():>int64=>{let x=fraction(42 1) return if x.numerator=?42 and x.denominator=?1 42 else 0}''',
]
# The diagnostic reads the complete record, but that branch cannot reach
# the final transfer. Keeping the same read on a returning path is different.
TERMINAL=SOURCE.replace('if value.size=?0 return Item[0 []]',
 'if value.size=?0 {printl(value) exit(101)}').replace('let empty=keep(Item[0 [99]])','let empty=Item[0 []]')
CASES.insert(-1,TERMINAL)
CURSOR=Path(__file__).resolve().parents[1]/'fixtures/consuming_cursor_caller.dewy'
CASES.insert(-1,CURSOR.read_text().replace('p"consuming_cursor_query.dewy"', f'p"{CURSOR.with_name("consuming_cursor_query.dewy")}"'))
UPDATE='''$explicit_copies
halve=(value:bigint):>bigint=>{
    $runtime_assert value >=? 0
    let remaining=value
    loop remaining >? 1 {remaining //= 2}
    return remaining
}
main=():>int64=>if halve(123456789012345678901234567890)=?1 42 else 0
'''
CASES.insert(-1,UPDATE)
ERRORS=[ALIAS.replace('let value=keep(Item[2 [20 22]])', 'let original=Item[2 [20 22]]\n let value=keep(original)\n original.values.clear'),
 TERMINAL.replace('printl(value) exit(101)', 'printl(value)'),
 OBSERVER.replace('size=(item:Item):>addr=>item.size', 'size=(item:Item):>addr=>{item.values.clear return item.size}'),
 ALIAS.replace('let owned=value', 'const owned=@value'),
]

@pytest.mark.parametrize('source',CASES)
def test_consuming_local_owner(tmp_path,source):
 path=tmp_path/'input.dewy'
 path.write_text(source)
 execute(tmp_path,'consuming-local',codegen(SrcFile.from_path(path),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_consuming_local_keeps_fallback(source):
 with pytest.raises(ReportException):codegen(SrcFile(None,source),debug_locations=False)


def test_native_consuming_local_owners(tmp_path):
 from test_bootstrap_structural_text import build_program_driver,check_structural_text
 check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)


def test_consumed_input_failure_keeps_diagnostic_value(tmp_path):
 source=CASES[-1].replace('fraction(42 1)', 'fraction(42 0)')
 for result in execute(tmp_path,'consumed-failure',codegen(SrcFile(None,source),debug_locations=False),expected=101):
  assert '`denominator` is 0' in result.stderr
