"""A binding is assigned only in the module that declared it: the prelude's and imports are shadowed with `let`."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source))


def test_a_bare_assignment_to_a_prelude_name_says_to_use_let() -> None:
    with pytest.raises(UserError, match='cannot assign to `run`: it belongs to the prelude') as caught:
        _check('run = (n:int64):>int64 => n')
    assert 'write `let run = …`' in str(caught.value)
    with pytest.raises(UserError, match='cannot assign to `ms`'):
        _check('ms = type of any & [x:int64]')   # the millisecond


def test_let_shadows_a_prelude_name() -> None:
    _check('let run = (n:int64):>int64 => n\nlet r:int64 = run(1)')
    _check('let ms = type of any & [x:int64]\nlet a = ms(x=1)')


def test_type_alias_assignment_reports_storage_or_origin() -> None:
    with pytest.raises(UserError, match='cannot assign to `Child`: it belongs to the prelude') as caught:
        _check('Child = type of [x:int64]')
    assert 'write `let Child = …`' in str(caught.value)
    with pytest.raises(UserError, match='assignment requires runtime storage'):
        _check('Node:type=[x:int64]\nNode = type of [y:int64]')
    _check('let Child=type of [x:int64]\nlet value=Child[42]')


def test_an_imported_binding_is_not_assignable_here(tmp_path) -> None:
    (tmp_path / 'lib.dewy').write_text('let counter:int64 = 0\nlet bump = ():>int64 => { counter += 1  return counter }\n')
    (tmp_path / 'main.dewy').write_text('from p"lib.dewy" import counter, bump\nmain = () => { counter = 5  exit(bump()) }\n')
    with pytest.raises(UserError, match='cannot assign to `counter`: it belongs to the module `lib.dewy`'):
        check.typecheck_and_resolve(SrcFile.from_path(tmp_path / 'main.dewy'))
    (tmp_path / 'main2.dewy').write_text('from p"lib.dewy" import bump\nmain = () => exit(bump() + bump())\n')   # the module itself still assigns it
    check.typecheck_and_resolve(SrcFile.from_path(tmp_path / 'main2.dewy'))


CASES = [
    'let capture=(n:int64):>int64=>n main=():>int64=>capture(42)',
    'let run=(n:int64):>int64=>n main=():>int64=>run(42)',
    'let counter:int64=0 bump=():>int64=>{counter+=21 return counter} '
    'main=():>int64=>{bump(); return bump()}',
]
ERRORS = [
    'capture=(n:int64):>int64=>n',
    'run=(n:int64):>int64=>n',
    'Child=type of [x:int64]',
    'let owner:int64=42 const view=@owner',
    'let owner:int64=42 let cursor=@owner',
]


@pytest.mark.parametrize('source', ERRORS)
def test_foreign_and_module_view_diagnostics(source):
    with pytest.raises(UserError):
        _check(source)


def test_native_foreign_assignments(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
    library=tmp_path/'lib.dewy'
    library.write_text('let counter:int64=0 let bump=():>int64=>{counter+=21 return counter}')
    check_structural_text(build_program_driver(tmp_path), tmp_path,
        cases=['from p"lib.dewy" import bump main=():>int64=>{bump(); return bump()}'],
        errors=['from p"lib.dewy" import counter main=():>int64=>{counter=42 return counter}',
                'from p"lib.dewy" import counter main=():>int64=>{counter+=42 return counter}',
                'from p"lib.dewy" import bump bump=():>int64=>42'])
