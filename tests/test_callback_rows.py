"""Callback row specialization, conversion and residual cost coverage."""
from pathlib import Path
import subprocess
import pytest
from tests.support import compiler
from tests.test_effect_rows import compile_source


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
def test_full_callback_rows(compiler, tmp_path, mode):
    source = Path(__file__).parent / 'ladder/74_callback_rows/design.dewy'
    result = compile_source(compiler, source, tmp_path, mode)
    assert result.returncode == 0, result.stdout + result.stderr
    if mode != 'check':
        ran = subprocess.run([tmp_path / 'program'], capture_output=True, text=True, timeout=10)
        assert (ran.returncode, ran.stdout) == (0, '9920 7\n'), ran.stderr

FLOWS = {
    'direct': 'return use_it(@FUNC)',
    'local': 'let f=@FUNC\nreturn use_it(@f)',
    'reassignment': 'let f=@pure\nf=@FUNC\nreturn use_it(@f)',
    'later_reassignment': 'let f=@pure\nlet result=use_it(@f)\nf=@FUNC\nreturn result',
    'record': 'let box=Holder[f=@FUNC]\nreturn use_it(@box.f)',
    'array': 'let fs=[@FUNC]\nreturn use_it(@fs[0])',
    'return': 'let f=make()\nreturn use_it(@f)',
    'partial': 'let f=@add(1)\nreturn use_it(@f)',
}


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
@pytest.mark.parametrize('flow', FLOWS)
@pytest.mark.parametrize('forbidden', [False, True])
def test_inferred_callback_sources(compiler, tmp_path, mode, flow, forbidden):
    selected = 'bad' if forbidden else 'pure'
    source = tmp_path / 'flow.dewy'
    source.write_text('''let shared:int64=0
pure=(x:int64):>int64=>x+1
bad=(x:int64):>int64=>{shared+=x; return x+1}
use_it=(f:<(x:int64):>int64 & no_effects>):>int64=>f(1)
Holder:type=[f:<(x:int64):>int64>]
''' + f'make=():><(x:int64):>int64>=>@{selected}\n'
      + f'add=(a:int64 x:int64):>int64=>{{return {selected}(a+x)-1}}\n'
      + 'main=():>int64=>{\n' + FLOWS[flow].replace('FUNC', selected) + '\n}\n')
    result = compile_source(compiler, source, tmp_path, mode)
    assert (result.returncode != 0) == forbidden, result.stdout + result.stderr
    if forbidden:
        assert 'effect' in result.stderr, result.stderr
        assert 'does not yet support' not in result.stderr
    elif mode != 'check':
        ran = subprocess.run([tmp_path / 'program'], capture_output=True, timeout=10)
        assert ran.returncode == 2, ran.stderr


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
@pytest.mark.parametrize('forbidden', [False, True])
def test_imported_alias_and_resources(compiler, tmp_path, mode, forbidden):
    (tmp_path / 'contracts.dewy').write_text('''Filesystem:type=[]
Disk:type=Filesystem
Action:type=<E:Effect>(<(x:int64):>int64 & E>)
# Inner E shadows the importing function's E; substitution is positional.
Forward:type=<T E:Effect>(Action<E>)
''')
    effect = 'mutates' if forbidden else 'reads'
    source = tmp_path / 'main.dewy'
    source.write_text('''from p"contracts.dewy" import Filesystem, Disk, Action, Forward
callback=(x:int64):>int64 & ''' + effect + '''<Filesystem>=>x+1
invoke=<E:Effect>(f:Forward<int64 E>):>int64 & E=>f(1)
restricted=(f:Action<no mutates<Disk>>):>int64 & no mutates<Filesystem>=>invoke(@f)
main=():>int64=>restricted(@callback)
''')
    result = compile_source(compiler, source, tmp_path, mode)
    assert (result.returncode != 0) == forbidden, result.stdout + result.stderr
    if forbidden:
        assert 'effect' in result.stderr
    elif mode != 'check':
        assert subprocess.run([tmp_path / 'program'], timeout=10).returncode == 2


@pytest.mark.core_quick
@pytest.mark.parametrize('declaration,message', [
    ('Bad:type=Action<int64>', 'expected Effect'),
    ('bad=<E:Effect>(x:E):>int64=>0', 'not a value type'),
    ('Bad:type=<T>(<(x:T):>T & T>)', 'Effect binder'),
    ('bad=():>int64 & allocates<Filesystem>=>0', 'effect'),
    ('bad=():>int64 & no_effects & allocates=>0', 'no_effects'),
    ('bad=():>int64 & reads<Filesystem> & no reads<Filesystem>=>0', 'contradictory'),
])
def test_effect_kind_errors(compiler, tmp_path, declaration, message):
    source = tmp_path / 'kind.dewy'
    # Instantiate otherwise-lazy aliases/signatures in the cases that need it.
    use = ''
    if declaration.startswith('Bad:type=Action'): use = 'let invalid:Bad\n'
    elif declaration.startswith('Bad:type=<T>'): use = 'let invalid:Bad<int64>\n'
    elif declaration.startswith('bad=<E:Effect>'): use = 'bad<no_effects>(1)\n'
    source.write_text('Filesystem:type=[]\nAction:type=<E:Effect>(<(x:int64):>int64 & E>)\n'
                      + declaration + '\nmain=():>int64=>{\n' + use + 'return 0\n}\n')
    result = compile_source(compiler, source, tmp_path, 'check')
    assert result.returncode != 0, result.stdout + result.stderr
    assert message in result.stderr, result.stderr


@pytest.mark.parametrize('explicit_place', [False, True])
def test_callback_place_is_not_nonlocal_remainder(compiler, tmp_path, explicit_place):
    permission = 'mutates<x> & ' if explicit_place else ''
    wrapper_permission = 'mutates<y> & ' if explicit_place else ''
    source = tmp_path / 'places.dewy'
    source.write_text('forward=<E:Effect>(f:<(@x:int64):>void & ' + permission
                      + 'E> @y:int64):>void & ' + wrapper_permission + 'E=>f(@y)\n'
                      'mutator=(@x:int64):>void & mutates<x>=>{x=7}\n'
                      'main=():>int64=>{let cell:int64=0; forward(@mutator @cell); return cell}\n')
    result = compile_source(compiler, source, tmp_path, 'check')
    assert (result.returncode == 0) == explicit_place, result.stderr
    if not explicit_place:
        assert 'callback-place permissions cannot flow into E' in result.stderr


@pytest.mark.parametrize('forbidden', [False, True])
def test_nested_callback_contravariance(compiler, tmp_path, forbidden):
    source = tmp_path / 'nested.dewy'
    source.write_text('''Pure:type=<(x:int64):>int64 & no_effects>
Plain:type=<(x:int64):>int64>
pure=(x:int64):>int64 & no_effects=>x+1
accept_any=(cb:Plain):>int64=>cb(1)
require_pure=(cb:Pure):>int64=>cb(1)
with_pure=(f:<(cb:Pure):>int64>):>int64=>f(@pure)
with_any=(f:<(cb:Plain):>int64>):>int64=>f(@pure)
main=():>int64=>''' + ('with_any(@require_pure)' if forbidden else 'with_pure(@accept_any)') + '\n')
    result = compile_source(compiler, source, tmp_path, 'default')
    assert (result.returncode != 0) == forbidden, result.stdout + result.stderr
    if not forbidden:
        assert subprocess.run([tmp_path / 'program'], timeout=10).returncode == 2


@pytest.mark.parametrize('captured', [False, True])
def test_closure_environment_inventory(compiler, tmp_path, captured):
    source = tmp_path / 'environment.dewy'
    capture = '($capture offset x:int64)' if captured else '(x:int64)'
    body = 'x+offset' if captured else 'x+1'
    source.write_text('main=():>int64=>{let offset:int64=1\nlet f=' + capture
                      + ':>int64 & no_effects=>' + body + '\nreturn f(1)}\n')
    result = compile_source(compiler, source, tmp_path, 'default')
    assert (result.returncode != 0) == captured, result.stdout + result.stderr
    if captured:
        assert 'effect contract violation' in result.stderr
    else:
        assert subprocess.run([tmp_path / 'program'], timeout=10).returncode == 2


@pytest.mark.parametrize('constrained', [False, True])
def test_reassignment_joins_declared_rows(compiler, tmp_path, constrained):
    source = tmp_path / 'reassign.dewy'
    source.write_text('''let shared:int64=0
pure=(x:int64):>int64 & no_effects=>x+1
bad=(x:int64):>int64 & reads<shared> & mutates<shared>=>{shared+=x; return x+1}
invoke=(f:<(x:int64):>int64 & no_effects>):>int64=>f(1)
main=():>int64=>{let f=@pure; f=@bad; return '''
                      + ('invoke(@f)' if constrained else 'f(1)') + '}\n')
    result = compile_source(compiler, source, tmp_path, 'default')
    assert (result.returncode != 0) == constrained, result.stdout + result.stderr
    if constrained:
        assert 'effect' in result.stderr
    else:
        assert subprocess.run([tmp_path / 'program'], timeout=10).returncode == 2


def test_demanded_nested_handle_summary(compiler, tmp_path):
    source = tmp_path / 'nested_handle.dewy'
    source.write_text('''leaf=(x:int64):>int64=>x+1
wrapper=(x:int64):>int64=>{let f=@leaf; return f(x)}
invoke=(f:<(x:int64):>int64 & no_effects>):>int64=>f(1)
main=():>int64=>invoke(@wrapper)
''')
    result = compile_source(compiler, source, tmp_path, 'default')
    assert result.returncode == 0, result.stdout + result.stderr
    assert subprocess.run([tmp_path / 'program'], timeout=10).returncode == 2


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
def test_shared_row_unions_callbacks(compiler, tmp_path, mode):
    source = tmp_path / 'join.dewy'
    source.write_text('''Filesystem:type=[]
Database:type=[]
Action:type=<E:Effect>(<():>int64 & E>)
first=():>int64 & reads<Filesystem>=>20
second=():>int64 & mutates<Database>=>22
twice=<E:Effect>(a:Action<E> b:Action<E>):>int64 & E=>a()+b()
main=():>int64=>twice(@first @second)
''')
    result = compile_source(compiler, source, tmp_path, mode)
    assert result.returncode == 0, result.stdout + result.stderr
    if mode != 'check':
        assert subprocess.run([tmp_path / 'program'], timeout=10).returncode == 42


@pytest.mark.parametrize('same_resource', [False, True])
def test_qualified_resources_remain_nominal(compiler, tmp_path, same_resource):
    (tmp_path / 'resources.dewy').write_text('Filesystem:type=[]\n')
    source = tmp_path / 'resource.dewy'
    permission = 'resources.Filesystem' if same_resource else 'Filesystem'
    source.write_text('''import p"resources.dewy" as resources
Filesystem:type=[]
reader=():>int64 & reads<resources.Filesystem>=>42
invoke=(f:<():>int64 & reads<''' + permission + '''>>):>int64=>f()
main=():>int64=>invoke(@reader)
''')
    result = compile_source(compiler, source, tmp_path, 'check')
    assert (result.returncode == 0) == same_resource, result.stdout + result.stderr
    if not same_resource:
        assert 'effect contract' in result.stderr


@pytest.mark.parametrize('aggregate', [False, True])
def test_extern_cannot_forge_callback_contract(compiler, tmp_path, aggregate):
    (tmp_path / 'contracts.dewy').write_text('''Pure:type=<(x:int64):>int64 & no_effects>
Holder:type=[f:Pure]
''')
    result_type = 'Holder' if aggregate else 'Pure'
    (tmp_path / 'foreign.jo').write_text("use 'contracts.dewy'\n"
                                      f'extern forged = () -> {result_type}\n'
                                      f'hidden = () -> {result_type}: forged()\n')
    source = tmp_path / 'extern.dewy'
    source.write_text('from p"foreign.jo" import hidden\n'
                      'main=():>int64=>{let value=hidden(); return 0}\n')
    result = compile_source(compiler, source, tmp_path, 'check')
    assert result.returncode != 0, result.stdout + result.stderr
    assert 'extern callable effect contracts require a checked implementation' in result.stderr


def test_explicit_row_is_not_widened(compiler, tmp_path):
    source = tmp_path / 'explicit.dewy'
    source.write_text('''Filesystem:type=[]
first=():>int64 & no_effects=>20
second=():>int64 & reads<Filesystem>=>22
twice=<E:Effect>(a:<():>int64 & E> b:<():>int64 & E>):>int64 & E=>a()+b()
main=():>int64=>twice<no_effects>(@first @second)
''')
    result = compile_source(compiler, source, tmp_path, 'check')
    assert result.returncode != 0, result.stdout + result.stderr
    assert 'callback effects exceed the explicit generic argument' in result.stderr
