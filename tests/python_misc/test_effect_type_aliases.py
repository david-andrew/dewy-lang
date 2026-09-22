"""Effect rows keep their kind and lexical identity through generic aliases."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ACTION='Action:type=<E:Effect>(():>int64 & E)\n'
CASES=[
    ACTION+'''quiet=():>int64 & no_effects=>42
main=():>int64=>{let f:Action<no_effects>=@quiet return f()}''',
    ACTION+'''let apply=<E:Effect>(f:Action<E>):>int64 & E=>f()
quiet=():>int64 & no_effects=>42
main=():>int64 & no_effects=>apply(@quiet)''',
    '''Mapper:type=<T E:Effect>((x:T):>T & E)
let apply=<T E:Effect>(f:Mapper<T E> x:T):>T & E=>f(x)
quiet=(x:int64):>int64 & no_effects=>x
main=():>int64 & no_effects=>apply(@quiet 42)''',
    '''Mapper:type=<T E:Effect>((x:T):>T & E)
Box:type=<T E:Effect>[callback:Mapper<T E>]
quiet=(x:int64):>int64 & no_effects=>x
main=():>int64=>{let box:Box<int64 no_effects>=[callback=(x:int64):>int64 & no_effects=>x] return box.callback(42)}''',
    ACTION+'''Filesystem=type of any
invoke=(f:Action<no mutates<Filesystem>>):>int64 & no mutates<Filesystem>=>f()
quiet=():>int64 & no_effects=>42
main=():>int64=>invoke(@quiet)''',
    ACTION+'''Filesystem=type of any
read=():>int64 & reads<Filesystem>=>42
main=():>int64=>{let f:Action<(reads<Filesystem> & no mutates<Filesystem>)>=@read return f()}''',
    ACTION+'''Again:type=<E:Effect>(Action<E>)
quiet=():>int64 & no_effects=>42
main=():>int64=>{let f:Again<Effect<>>=@quiet return f()}''',
]
ERRORS=[
    ACTION+'Bad:type=Action<int64>',
    'Box:type=<T>[value:T]\nBad:type=Box<no_effects>',
    'Bad:type=<E:Effect>[value:E]',
    ACTION+'Bad:type=Action<no_effects no_effects>',
    ACTION+'Bad:type=Action',
    ACTION+'''Filesystem=type of any
read=():>int64 & reads<Filesystem>=>42
main=():>int64=>{let f:Action<no_effects>=@read return f()}''',
    ACTION+'''Filesystem=type of any
invoke=(f:Action<reads<Filesystem>>):>int64 & no_effects=>f()''',
    ACTION+'''Filesystem=type of any
invoke=(f:():>int64):>int64 & no mutates<Filesystem>=>{
let secured:Action<no mutates<Filesystem>>=@f return secured()}''',
    ACTION+'Bad:type=Action<(int64 & no_effects)>',
    ACTION+'''Filesystem=type of any Other=type of any
read=():>int64 & reads<Filesystem>=>42
main=():>int64=>{let f:Action<reads<Other>>=@read return f()}''',
]

@pytest.mark.parametrize('source',CASES)
def test_effect_row_alias(source,tmp_path):
    execute(tmp_path,'effect-alias',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_effect_alias_preserves_kinds_and_contracts(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source))

def imported_alias(tmp_path):
    module=tmp_path/'callbacks.dewy'
    module.write_text(ACTION+'Box:type=<T>[value:T]\n')
    return f'''import p"{module}" as callbacks
quiet=():>int64 & no_effects=>42
main=():>int64=>{{let f:callbacks.Action<no_effects>=@quiet
let box:callbacks.Box<int64>=[value=f()] return box.value}}'''

def test_imported_effect_alias(tmp_path):
    source=tmp_path/'main.dewy'
    source.write_text(imported_alias(tmp_path))
    execute(tmp_path,'imported-effect-alias',codegen(SrcFile.from_path(source)))

def test_native_effect_aliases(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=[*CASES,imported_alias(tmp_path)],errors=ERRORS)


def check_effect_alias_cache(binary, tmp_path):
    import os
    import subprocess
    from test_bootstrap_lowering import ROOT
    prelude=tmp_path/'alias-prelude.dewy'
    prelude.write_text(ACTION)
    source=tmp_path/'cached-alias.dewy'
    source.write_text('quiet=():>int64 & no_effects=>42\nmain=():>int64=>{let f:Action<no_effects>=@quiet return f()}')
    cache=tmp_path/'alias-cache'
    command=[binary,source,ROOT/'library',cache,prelude]
    env=os.environ.copy()
    env.pop('DEWY_NO_PRELUDE_CACHE',None)
    emitted=[]
    for expected in ('miss','hit'):
        env['DEWY_TEST_PRELUDE_CACHE']=expected
        result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stderr
        emitted.append(result.stdout)
    assert emitted[0]==emitted[1]
    execute(tmp_path,'cached-effect-alias',emitted[1])
    source.write_text('Bad:type=Action<int64>\nmain=():>int64=>42')
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=120)
    assert result.returncode==1 and 'effect row' in result.stderr,result.stderr


def test_native_effect_alias_cache(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    check_effect_alias_cache(build_program_driver(tmp_path),tmp_path)
