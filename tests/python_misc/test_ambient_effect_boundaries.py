"""Activation-local captures stay visible inside, but do not become ambient effects."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, Span, ReportException
from dewy.semantic import hir, ty
from dewy.semantic.analyze.effects import analyze_global_writes
from test_bootstrap_effects import emit_hir
from test_scalar_projection import execute

ROOT=Path(__file__).resolve().parents[2]
LOC=Span(0,0)
SIGNATURE=ty.FunctionType([],[],None,'void')


def program():
    def read(binding, type_='int64'):
        return hir.ExpressedIdentifier(LOC,type_,f'b{binding}',binding_id=binding)
    def number():
        return hir.Integer(LOC,'int64','0d',0)
    def assign(binding):
        return hir.Assign(LOC,'void',read(binding),'=',number())
    def call(binding):
        return hir.FunctionCall(LOC,'void',read(binding,SIGNATURE),[],{})
    def declaration(binding,body,params=()):
        literal=hir.FunctionLiteral(LOC,SIGNATURE,list(params),[],None,'void',hir.Block(LOC,'void',body,True))
        return hir.Declare(LOC,'void','let',f'b{binding}',SIGNATURE,literal,binding_id=binding)
    def local(binding):
        return hir.Declare(LOC,'void','let',f'b{binding}','int64',number(),binding_id=binding)
    nested_call=call(101)
    outer_call=call(100)
    recursive_call=call(100)
    # b2 belongs to the outer activation. The nested invocation writes it;
    # calling outer creates its own b2 even along the recursive edge.
    nested=declaration(101,[assign(1),assign(2)])
    outer=declaration(100,[local(2),nested,nested_call,recursive_call])
    param_call=call(102)
    parameter=declaration(102,[assign(3)],[hir.Param('b3','int64',binding_id=3)])
    unknown_call=call(104)
    unknown_outer_call=call(103)
    unknown=declaration(103,[local(4),unknown_call])
    root=hir.Block(LOC,'void',[outer,parameter,unknown,outer_call,param_call,unknown_outer_call],True)
    expected=[(nested_call,{1,2}),(outer_call,{1}),(recursive_call,{1}),
              (param_call,set()),(unknown_call,{1,2,3,4}),(unknown_outer_call,{1,2,3})]
    return root,expected


def test_ambient_effects_stop_private_captures_at_the_owner_boundary():
    root,expected=program()
    actual=analyze_global_writes(root,{1,2,3,4})
    for call,writes in expected:
        assert actual[id(call)]==writes


def test_native_ambient_effects_match_hosted(tmp_path):
    root,expected=program()
    lines,root_id,names=emit_hir(root,with_names=True)
    checks=[]
    for index,(call,writes) in enumerate(expected):
        checks.append(f"    $runtime_assert {names[id(call)]} in? result\n    loop binding in result[{names[id(call)]}] {{printl(\"{index}:{{binding}}\")}}")
    source=tmp_path/'ambient-effects.dewy'
    source.write_text(f'''from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/effects.dewy'}" as effects
main=():>int64=>{{
    let span=Span[0 0]
    let nodes:array<hir.AST>=[]
    let type_nodes=types.Table[]
    let scalar=types.primitive('any' @type_nodes)
    let callable=types.function_type([] [] none scalar [] @type_nodes)
{chr(10).join(lines)}
    let result=effects.analyze_global_writes({root_id} nodes set[1 2 3 4])
{chr(10).join(checks)}
    return 42
}}
''')
    rows=sorted(f'{i}:{binding}' for i,(_,writes) in enumerate(expected) for binding in writes)
    for result in execute(tmp_path,'ambient-effects',codegen(SrcFile.from_path(source),debug_locations=False)):
        assert sorted(result.stdout.splitlines())==rows


HELPER='''compute=():>int64=>{let private:int64=40
read=():>int64=>private
private=read()+2 return read()}
set=(@value:int64 result:int64):>void=>{value=result}
'''
CASES=[HELPER+'''forward=(@table:dict<string int64>):>int64=>{
if 'x' in? table {set(@table['x'] compute()) return table['x']} return 1}
main=():>int64=>{let table:dict<string int64>=['x'->0] return forward(@table)}''',
       HELPER+'''write=(@value:int64):>void=>{value=compute()}
forward=(@table:dict<string int64>):>int64=>{
if 'x' in? table {write(@table['x']) return table['x']} return 1}
main=():>int64=>{let table:dict<string int64>=['x'->0] return forward(@table)}''']
ERRORS=['''set=(@value:int64 result:int64):>void=>{value=result}
main=():>int64=>{let table:dict<string int64>=['x'->0]
clear=():>int64=>{table.clear return 42}
set(@table['x'] clear()) return 42}''']

@pytest.mark.parametrize('source',CASES)
def test_private_callback_work_keeps_the_caller_entry_stable(tmp_path,source):
    execute(tmp_path,'private-capture',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_actual_owner_captures_still_invalidate_the_entry(source):
    with pytest.raises(ReportException,match='invalidate a selected dictionary entry'):
        codegen(SrcFile(None,source),debug_locations=False)


def test_native_private_capture_lifetimes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
