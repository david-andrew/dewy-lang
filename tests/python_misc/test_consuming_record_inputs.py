"""Known single-use append inputs transfer storage through direct-call chains."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute


HEADER = '''Box:type=[items:array<int64>]
append=(@rows:array<Box> value:Box):>void=>{rows.push(value)}
'''
MAIN = '''probe=():>int64=>{let rows:array<Box>=[] append(@rows Box[[42]])
if rows.length>?0 and rows[0].items.length>?0 return rows[0].items[0]
return 1}
main=():>int64=>{if probe() not=?42 return 1
let before:int64=_arena_live_bytes
loop i in [0..100) {if probe() not=?42 return 2}
$runtime_assert _arena_live_bytes=?before
return 42}
'''
CASES = [HEADER + MAIN,
    HEADER + '''forward=(value:Box @output:array<Box>):>void=>append(value=value rows=@output)
''' + MAIN.replace('append(@rows Box[[42]])', 'forward(Box[[42]] @rows)'),
    HEADER + MAIN.replace('append(@rows Box[[42]])',
                          'let value=Box[[42]] append(@rows value)'),
    HEADER + MAIN.replace('append(@rows Box[[42]])',
                          'let value=Box[[42]] append(@rows value.copy()) value.items.clear()'),
    (HEADER + MAIN).replace('rows.push(value)', 'rows.insert(value 0)'),
    HEADER + '''modify=(value:Box):>Box=>{value.items.push(42) return value}
''' + MAIN.replace('append(@rows Box[[42]])', 'append(@rows modify(Box[[]]))'),
]
# A long reverse-declared chain exercises propagation from a real endpoint.
CHAIN = ''.join(f'f{i}=(value:Box @rows:array<Box>):>void=>f{i+1}(value @rows)\n'
                for i in range(12)) + 'f12=(value:Box @rows:array<Box>):>void=>append(@rows value)\n'
CASES.append(HEADER + CHAIN + MAIN.replace('append(@rows Box[[42]])', 'f0(Box[[42]] @rows)'))

ERRORS = [
    HEADER.replace('rows.push(value)', 'rows.push(value) rows.push(value)') + MAIN,
    HEADER.replace('rows.push(value)', 'if rows.length<?10 {rows.push(value)}') + MAIN,
    HEADER + MAIN.replace('append(@rows Box[[42]])',
                          'let value=Box[[42]] append(@rows value) value.items.clear()'),
    HEADER + MAIN.replace('append(@rows Box[[42]])',
                          'let callback=@append callback(@rows Box[[42]])'),
    HEADER + MAIN.replace('append(@rows Box[[42]])',
                          'let value=Box[[42]] const saved=@value append(@rows value) if saved.items.length=?0 return 3'),
]


@pytest.mark.parametrize('source', CASES)
def test_consuming_record_inputs(tmp_path, source):
    execute(tmp_path, 'consuming-record', codegen(SrcFile(None, '$explicit_copies\n'+source),
                                                debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_consuming_inputs_retain_copy_obligations(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n'+source), debug_locations=False)


def test_native_consuming_record_inputs(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=['$explicit_copies\n'+source for source in CASES],
                          errors=['$explicit_copies\n'+source for source in ERRORS])
