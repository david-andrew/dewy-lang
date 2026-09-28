"""Direct mutable record calls own one value, rather than copying twice."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HEADER = '''Pack:type=[text:string values:array<int64>]
make=():>Pack=>Pack['owned' [2]]
change=(p:Pack):>int64=>{
    p.values.push(40)
    return if p.values.length>?1 p.values[0]+p.values[1] else 0
}
'''
MOVE = HEADER + '''main=():>int64=>{let p=make() return change(p)}'''
FRESH = HEADER + '''main=():>int64=>change(make())'''
KEPT = HEADER + '''main=():>int64=>{
    let p=make()
    let result=change(p)
    return if p.values.length=?1 result else 0
}'''
VIEW = KEPT.replace('    let result=change(p)', '    const held=@p\n    let result=change(p)').replace('if p.values.length=?1', 'if held.values.length=?1')
REPEAT = HEADER + '''main=():>int64=>{
    let p=make()
    loop i in [0..2) {if change(p) not=?42 return 0}
    return 42
}'''
CALLBACK = HEADER + '''apply=(f:(p:Pack):>int64 p:Pack):>int64=>f(p)
main=():>int64=>{let p=make() let result=apply(@change p) return if p.values.length=?1 result else 0}'''
REBOUND = HEADER.replace('    p.values.push(40)', "    p=Pack['new' [2 40]]") + 'main=():>int64=>{let p=make() return change(p)}'
FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures/owned_record_parameters.dewy').read_text()
ALIASED = HEADER + """main=():>int64=>{
    let p=make()
    let snapshot=p.copy()
    let result=change(p)
    return if snapshot.values.length=?1 and snapshot.values[0]=?2 result else 0
}"""
KEYWORD = MOVE.replace('change(p)}', 'change(p=p)}')
BRANCH = HEADER + """probe=(flag:bool):>int64=>{
    let p=make()
    if flag return change(p)
    return if p.values.length=?1 42 else 0
}
main=():>int64=>if probe(true)=?42 probe(false) else 0"""
LATER = HEADER + """read=(p:Pack old:int64):>int64=>{p.values.clear return old+40}
main=():>int64=>{
    let p=make()
    if p.values.length=?0 return 0
    return read(p p.values[0])
}"""
CASES = [LATER, MOVE, FRESH, KEPT, VIEW, REPEAT, CALLBACK, REBOUND, FIXTURE, ALIASED, KEYWORD, BRANCH]

@pytest.mark.parametrize('source', CASES)
def test_owned_record_call(tmp_path, source):
    execute(tmp_path, 'owned-record', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', [MOVE, FRESH, REBOUND, ALIASED, KEYWORD, BRANCH])
def test_owned_record_call_needs_no_copy(tmp_path, source):
    execute(tmp_path, 'strict-owned-record', codegen(SrcFile(None, '$explicit_copies\n'+source), debug_locations=False))

@pytest.mark.parametrize('source', [KEPT, VIEW, REPEAT, CALLBACK, LATER])
def test_live_record_call_still_needs_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n'+source), debug_locations=False)


def test_native_owned_record_parameters(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
        cases=CASES+['$explicit_copies\n'+source for source in [MOVE,FRESH,REBOUND,ALIASED,KEYWORD,BRANCH]],
        errors=['$explicit_copies\n'+source for source in [KEPT,VIEW,REPEAT,CALLBACK,LATER]])


def test_record_call_allocation_budget_has_positive_control(tmp_path, monkeypatch):
    optimized = codegen(SrcFile(None, FIXTURE), debug_locations=False)
    with monkeypatch.context() as patch:
        patch.setattr(lower._Lowerer, '_adopt_object_fields', lambda *args, **kwargs: None)
        copied = codegen(SrcFile(None, FIXTURE.replace('$explicit_copies\n', '')), debug_locations=False)
    execute(tmp_path, 'owned-budget', optimized)
    execute(tmp_path, 'copied-budget', copied, expected=1)
