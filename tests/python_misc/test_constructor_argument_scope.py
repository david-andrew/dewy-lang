"""Explicit constructor arguments use the caller; defaults see earlier fields."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

SWAP = '''Term:type=const [id:int64]
Pair:type=const [left:Term right:Term]
swap=(left:Term right:Term):>Pair=>Pair[right left]
main=():>int64=>{
    let result=swap(Term[8] Term[4])
    return if result.left.id=?4 and result.right.id=?8 42 else 1
}'''
CASES = [SWAP, SWAP.replace('Pair[right left]', 'Pair[right=left left=right]'),
    '''Pair:type=const [left:int64 right:int64=left]
    main=():>int64=>{
        let left:int64=7
        let explicit=Pair[1 left]
        let defaulted=Pair[2]
        return if explicit.right=?7 and defaulted.right=?2 42 else 1
    }''',
    '''Sized:type=const [alphabet:string count:int64=alphabet.length]
    main=():>int64=>{
        let alphabet='abc'
        let explicit=Sized['x' alphabet.length]
        let defaulted=Sized['ab']
        return if explicit.count=?3 and defaulted.count=?2 42 else 1
    }''',
]
CASES.append('let left:int64=7\nHolder:type=[left:int64 run:():>int64]\nmain=():>int64=>{\n    let constructed=Holder[1 ():>int64=>left]\n    let literal=[left=2 run=():>int64=>left]\n    return if constructed.run()=?7 and literal.run()=?2 42 else 1\n}')
ERRORS = ["Sized:type=const [alphabet:string count:int64<count=?alphabet.length>=alphabet.length]\nmain=():>int64=>{\n    let alphabet='abc'\n    let invalid=Sized['x' alphabet.length]\n    return 42\n}"]


def test_constructor_contract_still_names_constructed_siblings():
    with pytest.raises(ReportException, match="refinement refuted"):
        codegen(SrcFile(None, ERRORS[0]), debug_locations=False)



@pytest.mark.parametrize('source', CASES)
def test_constructor_arguments_keep_caller_scope(tmp_path, source):
    execute(tmp_path, 'constructor-scope', codegen(SrcFile(None, source), debug_locations=False))


def test_native_constructor_arguments_keep_caller_scope(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
