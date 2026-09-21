"""A borrowed component can change without replacing its containing storage."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute


CASES = [
    '''set=(@n:int64):>void=>{n=42}
main=():>int64=>{
    let box:[items:array<int64> other:int64]=[[1] 42]
    set(@box.items[0])
    $assert box.items.length=?1
    $assert box.other=?42
    return box.items[0]
}''',
    '''clear=(@xs:array<int64>):>void=>xs.clear
main=():>int64=>{
    let box:[left:array<int64> right:array<int64>]=[[1] [42]]
    clear(@box.left)
    $assert box.right.length=?1
    return box.right[0]
}''',
]

ERRORS = [
    '''clear=(@box:[items:array<int64>]):>void=>box.items.clear
main=():>int64=>{
    let root:[child:[items:array<int64>]]=[[[42]]]
    clear(@root.child)
    return root.child.items[0]
}''',
    '''clear=(@xs:array<int64>):>void=>xs.clear
main=():>int64=>{
    let xs:array<array<int64>>=[[42]]
    if xs.length not=?1 or xs[0].length not=?1 return 1
    clear(@xs[0])
    return xs[0][0]
}''',
    '''set=(@n:int64):>void=>{n=1}
main=():>int64=>{
    let box:[items:array<int64>]=[[42]]
    if box.items[0] not=?42 return 1
    set(@box.items[0])
    $assert box.items[0]=?42
    return 42
}''',
]


@pytest.mark.parametrize('source', CASES)
def test_component_place_preserves_parent_and_sibling_facts(tmp_path, source):
    execute(tmp_path, 'place-facts', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_component_place_discards_written_and_descendant_facts(source):
    with pytest.raises(ReportException, match='bounds|assert'):
        codegen(SrcFile(None, source))


def test_native_projected_place_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text

    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
