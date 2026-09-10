"""An implicit method receiver has the same write barriers as explicit @."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import TypeCheckError, UserError

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
