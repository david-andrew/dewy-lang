"""Nested record fields use last-use evidence and report retained snapshots."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen, lower
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

HEADER = '''Inner:type=[text:string values:array<int64>]
Outer:type=[child:Inner]
make=():>Inner=>Inner['owned' [42]]
read=(value:Outer):>int64=>if value.child.values.length>?0 value.child.values[0] else 0
'''
MOVE = HEADER + '''main=():>int64=>{
    let source=make()
    let target=Outer[source]
    return read(target)
}'''
LIVE = HEADER + '''main=():>int64=>{
    let source=make()
    let target=Outer[source]
    target.child.values.clear
    return if source.values.length>?0 source.values[0] else 0
}'''
VIEW = LIVE.replace('    let target=Outer[source]', '    const held=@source\n    let target=Outer[source]').replace('if source.values.length>?0 source.values[0]', 'if held.values.length>?0 held.values[0]')
LATER = MOVE.replace('Outer:type=[child:Inner]', 'Outer:type=[child:Inner seen:int64]').replace('Outer[source]', 'Outer[source source.values.length]').replace('return read(target)', 'return if target.seen=?1 read(target) else 0')
REPEAT = MOVE.replace('    let target=Outer[source]\n    return read(target)', '    loop i in [0..2) {let target=Outer[source] if read(target) not=?42 return 0}\n    return 42')
SHARED = LIVE.replace('    let target=Outer[source]', '    let snapshot=source.copy()\n    let target=Outer[source]').replace('if source.values.length>?0 source.values[0]', 'if snapshot.values.length>?0 snapshot.values[0]')
FRESH = MOVE.replace('    let source=make()\n    let target=Outer[source]', '    let target=Outer[make()]')
EXPLICIT = LIVE.replace('Outer[source]', 'Outer[source.copy()]')
NESTED = MOVE.replace('Outer:type=[child:Inner]', 'Middle:type=[inside:Inner]\nOuter:type=[child:Middle]').replace('value.child.values', 'value.child.inside.values').replace('    let target=Outer[source]', '    let middle=Middle[source]\n    let target=Outer[middle]')
FIXED = MOVE.replace('values:array<int64>', 'values:array<int64 length=1>')
BRANCH = HEADER + '''probe=(yes:bool):>int64=>{
    let source=make()
    if yes {let target=Outer[source] return read(target)}
    return if source.values.length>?0 source.values[0] else 0
}
main=():>int64=>if probe(true)=?42 probe(false) else 0'''
FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures/record_field_moves.dewy').read_text()
REPLACEMENT_FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures/record_field_replacement_moves.dewy').read_text()
KERNELS = [FIXTURE, REPLACEMENT_FIXTURE]
STRICT = [MOVE, SHARED, FRESH, EXPLICIT, NESTED, BRANCH]
COPIES = [LIVE, VIEW, LATER, REPEAT]
# Replacing an existing field has the same transfer proof, plus releasing
# the old field after the replacement is acquired.
for source in [MOVE, SHARED, EXPLICIT, BRANCH]:
    STRICT.append(source.replace('let target=Outer[source]', "let target=Outer[make()] target.child=source").replace('let target=Outer[source.copy()]', "let target=Outer[make()] target.child=source.copy()"))
for source in [LIVE, VIEW, LATER, REPEAT]:
    if source is LATER:
        continue  # this counterexample specifically reads a later constructor operand
    COPIES.append(source.replace('let target=Outer[source]', 'let target=Outer[make()] target.child=source'))

@pytest.mark.parametrize('source', STRICT)
def test_last_use_record_moves_into_field(tmp_path, source):
    execute(tmp_path, 'record-field', codegen(SrcFile(None, '$explicit_copies\n'+source), debug_locations=False))

@pytest.mark.parametrize('source', COPIES + [FIXED, *KERNELS])
def test_record_field_values_and_cleanup(tmp_path, source):
    execute(tmp_path, 'record-field-values', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', COPIES)
def test_live_record_field_copy_is_reported(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n'+source), debug_locations=False)


@pytest.mark.parametrize('fixture', KERNELS)
def test_record_field_budget_positive_control(tmp_path, monkeypatch, fixture):
    optimized = codegen(SrcFile(None, fixture), debug_locations=False)
    with monkeypatch.context() as patch:
        patch.setattr(lower._Lowerer, '_adopt_object_fields', lambda *args, **kwargs: None)
        copied = codegen(SrcFile(None, fixture.replace('$explicit_copies\n', '')), debug_locations=False)
    execute(tmp_path, 'field-budget', optimized)
    execute(tmp_path, 'field-copy-budget', copied, expected=1)


def test_native_record_field_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
        cases=['$explicit_copies\n'+source for source in STRICT]+COPIES+[FIXED,*KERNELS],
        errors=['$explicit_copies\n'+source for source in COPIES])
