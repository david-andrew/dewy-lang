"""An implicit method receiver has the same write barriers as explicit @."""
import pytest
from pathlib import Path

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import TypeCheckError, UserError
from dewy.reporting import ReportException
from dewy.backend.udewy import codegen
from tests.python_misc.test_scalar_projection import execute

METHOD = 'T:type=[x:int64 set=(n:int64)=>{x=n}]\n'


@pytest.mark.parametrize('body', [
    'const t=T[1]\nt.set(2)',
    'const outer=[t=T[1]]\nouter.t.set(2)',
    'let outer=[const t=T[1]]\nouter.t.set(2)',
    'Outer:type=const[t:T]\nlet outer=Outer[T[1]]\nouter.t.set(2)',
    'let values=[T[1]]\nloop t in values {t.set(2)}',
])
def test_method_receiver_cannot_bypass_read_only_storage(body):
    with pytest.raises(UserError, match='const|immutable|borrowed|read.only'):
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + METHOD + body))


def test_copied_receiver_can_change_independently():
    check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + METHOD +
        'const t=T[1]\nlet copy=t\ncopy.set(2)'))


@pytest.mark.parametrize('method, call', [
    ('clear=()=>{data.clear}', 'clear'),
])
def test_implicit_mutation_expires_nested_membership(method, call):
    source = ('T:type=[data:dict<string int64> ' + method + ']\n'
        'let t=T[["a"->1]]\n'
        'if "a" in? t.data {t.' + call + ' let x:int64=t.data["a"]}')
    with pytest.raises(UserError, match='dictionary key is not proven present'):
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


def test_method_call_expires_field_type_narrowing():
    source = ('T:type=[x:int64|string set=()=>{x="no"}]\n'
        'let t=T[1]\nif t.x is? int64 {t.set t.x+1}')
    with pytest.raises(TypeCheckError):
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


@pytest.mark.parametrize('field', ['int64<v=>v>=?0>', 'int64<v=>v<=?42>'])
@pytest.mark.parametrize('call', ['d.reset()', 'reset(@d)'])
def test_parent_place_cannot_weaken_child_field_storage(field, call):
    source = ('Parent=type of [token:int64 reset=():>void=>{token=-1}]\n'
              f'Derived=type of Parent & [token:{field}]\n'
              'reset=(@value:Parent):>void=>{value.token=-1}\n'
              f'f=():>void=>{{let d=Derived[1] {call}}}')
    with pytest.raises(ReportException, match='place parameter types are invariant'):
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


def test_unchanged_parent_field_storage_remains_compatible():
    source = ('Parent=type of [token:int64 reset=():>void=>{token=-1}]\n'
              'Derived=type of Parent & [extra:string]\n'
              'f=():>void=>{let d=Derived[1 "kept"] d.reset()}')
    check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


def test_read_only_parent_method_accepts_strengthened_child():
    source = ('Parent=type of [token:int64 read=():>int64=>token]\n'
              'Derived=type of Parent & [token:int64<v=>v>=?0>]\n'
              'f=():>int64=>{let d=Derived[42] return d.read()}')
    check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


def test_nominal_parent_prefix_executes_on_both_targets(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'fixtures/nominal_place_prefix.dewy'
    execute(tmp_path, 'nominal_prefix', codegen(SrcFile.from_path(source)))
