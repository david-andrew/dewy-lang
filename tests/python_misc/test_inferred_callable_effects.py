"""Selected callable boundaries are checked against final body effects."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ACCEPTED = [
    '''apply=(f:():>int64 & no_effects):>int64 & no_effects=>f()
answer=():>int64=>42
main=():>int64 & no_effects=>apply(@answer)''',
    '''let apply=<E:Effect>(f:():>int64 & E):>int64 & E=>f()
answer=():>int64=>42
main=():>int64 & no_effects=>apply(@answer)''',
    '''apply=(f:(n:int64):>int64 & no_effects):>int64 & no_effects=>f(3)
a=(n:int64):>int64=>{if n <=? 0 return 42 return b(n-1)}
b=(n:int64):>int64=>{if n <=? 0 return 42 return a(n-1)}
main=():>int64 & no_effects=>apply(@a)''',
    '''let identity=<T>(x:T):>T=>x
apply=(f:():>int64 & no_effects):>int64 & no_effects=>f()
answer=():>int64=>identity(42)
main=():>int64 & no_effects=>apply(@answer)''',
    '''one=():>int64=>21
other=():>int64=>42
main=():>int64=>{let first=@one first=@other return first()}''',
]
REJECTED = [
    '''let state:int64=0
apply=(f:():>int64 & no_effects):>int64 & no_effects=>f()
answer=():>int64=>{state+=1 return 42}
main=():>int64=>apply(@answer)''',
    '''apply=(f:():>int64 & no_effects):>int64 & no_effects=>f()
unknown=(f:():>int64):>int64=>apply(@f)
main=():>int64=>42''',
    '''let state:int64=0
let chosen=():>int64=>42
noisy=():>int64=>{state+=1 return 42}
main=():>int64 & no_effects=>{chosen=@noisy return chosen()}''',
    '''let state:int64=0
apply=(f:():>int64 & no_effects):>int64 & no_effects=>f()
a=():>int64=>b()
b=():>int64=>{state+=1 return 42}
main=():>int64=>apply(@a)''',
]

@pytest.mark.parametrize('source', ACCEPTED)
def test_inferred_callback_executes(source, tmp_path):
    execute(tmp_path, 'inferred-callback', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', REJECTED)
def test_inferred_callback_rejects_effectful_boundary(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

# Joining or reassigning a handle must not conflate its row with its source's.
@pytest.mark.parametrize('source', [
    '''a=():>int64=>21
b=():>int64=>42
choose=(yes:bool):>int64=>{let f=if yes @b else @a return f()}
main=():>int64 & no_effects=>choose(true)''',
    '''let state:int64=0
pure=():>int64=>42
noisy=():>int64=>{state+=1 return 21}
apply=(f:():>int64 & no_effects):>int64 & no_effects=>f()
main=():>int64=>{let f=@pure f=@noisy let ignored=f() return apply(@pure)}''',
])
def test_callable_rows_join_without_rewriting_source_contract(source, tmp_path):
    execute(tmp_path, 'callback-joins', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', [
    '''let state:int64=0
a=():>int64=>42
b=():>int64=>{state+=1 return 42}
choose=(yes:bool):>int64 & no_effects=>{let f=if yes @b else @a return f()}
main=():>int64=>choose(true)''',
    '''let state:int64=0
a=():>int64=>42
b=():>int64=>{state+=1 return 42}
apply=(f:():>int64 & no_effects):>int64 & no_effects=>f()
choose=(yes:bool):>int64=>{let f=if yes @b else @a return apply(@f)}
main=():>int64=>choose(true)''',
])
def test_callable_join_does_not_discard_an_effectful_alternative(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_inferred_callback_retains_lifecycle_effects():
    from pathlib import Path
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/inferred_callable_lifecycle_rejected.dewy'
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile.from_path(fixture))


def test_union_of_different_callable_shapes_retains_every_effect_row():
    source = '''let state:int64=0
left=(a:int64):>int64=>a
right=(b:int64):>int64=>{state+=1 return b}
apply=(f:(int64):>int64 & no_effects):>int64 & no_effects=>f(42)
choose=(yes:bool):>int64=>{let f=if yes @left else @right return apply(@f)}
main=():>int64=>choose(false)'''
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_inferred_callback_effects(tmp_path):
    from pathlib import Path
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    fixtures = Path(__file__).resolve().parents[1] / 'fixtures'
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[(fixtures / 'inferred_callable_effects.dewy').read_text()],
                          errors=[(fixtures / 'inferred_callable_lifecycle_rejected.dewy').read_text()])


def test_reassigning_an_inferred_handle_to_a_literal_widens_its_storage_row(tmp_path):
    source = '''let state:int64=0
answer=():>int64=>42
main=():>int64=>{let f=@answer f=():>int64=>{state+=1 return 42} return f()}'''
    execute(tmp_path, 'literal-reassignment', codegen(SrcFile(None, source)))
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source.replace('main=():>int64=>', 'main=():>int64 & no_effects=>')))
