"""Read-only branch selections share stable storage, with bounded fresh arms."""
from pathlib import Path

import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/array_selection_views.dewy').read_text()
CASES = [
    SOURCE,
    SOURCE.replace('if flag xs else [42]', 'if flag xs else if flag [] else [42]'),
    SOURCE.replace('if flag xs else [42]', 'if flag [42] else xs'),
    SOURCE.replace('    const selected:', '    let local=[42]\n    const selected:')
          .replace('if flag xs else [42]', 'if flag xs else local'),
    SOURCE.replace('choose=(xs:array<int64> flag:bool)', 'Box:type=[items:array<int64>]\nchoose=(box:Box flag:bool)')
          .replace('if flag xs else [42]', 'if flag box.items else [42]')
          .replace('choose(xs true)', 'choose(Box[xs] true)').replace('choose(xs false)', 'choose(Box[xs] false)'),
    '''$explicit_copies
pick=(xs:array<int64> ys:array<int64> flag:bool):>int64 & no_effects=>{
 const values=if flag xs else ys
 return if values.length>?0 values[0] else 0
}
main=():>int64=>{return if pick([42] [1] true)=?42 and pick([1] [42] false)=?42 42 else 1}''',
    # Owning returns still copy; clearing the result cannot clear the input.
    '''pick=(xs:array<int64> flag:bool):>array<int64>=>{
 const values:array<int64>=if flag xs else [42]
 return values
}
main=():>int64=>{let xs:array<int64>=[42] let result=pick(xs true)
result.clear() return if xs.length=?1 42 else 1}''',
]
CASES.extend([
    """pick=(xs:array<int64> flag:bool):>int64=>{
 const selected:array<int64>=if flag xs else [42]
 xs.clear()
 return if selected.length>?0 selected[0] else 1
}
main=():>int64=>pick([42] true)""",
    """work=(flag:bool):>int64=>{
 let xs:array<int64>=[42]
 const selected:array<int64>=if flag xs else []
 let changed=xs
 changed.clear()
 return if selected.length>?0 selected[0] else 1
}
main=():>int64=>work(true)""",
    """$explicit_copies
Box:type=[items:array<int64>]
work=(box:Box flag:bool):>int64=>{
 const selected:array<int64>=if flag box.items else []
 return if selected.length>?0 selected[0] else 1
}
main=():>int64=>work(Box[[42]] true)""",
])

CASES.extend([
    SOURCE.replace('choose=', 'read=(values:array<int64>):>int64 & no_effects=>if values.length>?0 values[0] else 0\nchoose=', 1)
          .replace('    if selected.length>?0 return selected[0]\n    return 0', '    return read(selected)'),
    """$explicit_copies
make=():>array<int64>=>[42]
work=(flag:bool):>int64=>{
 let owner=make()
 const selected:array<int64>=if flag owner else [42]
 return if selected.length>?0 selected[0] else 1
}
main=():>int64=>if work(true)=?42 and work(false)=?42 42 else 2""",
])

CASES.extend([
    """main=():>int64=>{const value=if true 42 else 0 return value}""",
    """pick=(flag:bool):>int64=>{const value=if flag {let x=42 x} else 0 return value}
main=():>int64=>pick(true)""",
])

ERRORS = [
    SOURCE.replace('    if selected.length', '    xs.clear()\n    if selected.length'),
    SOURCE.replace('    if selected.length', '    selected.clear()\n    if selected.length'),
    SOURCE.replace('[42]\n    if selected.length', '['+' '.join(['42']*65)+']\n    if selected.length'),
    SOURCE.replace('    const selected:', '    const selected:').replace('else [42]', 'else xs.copy()'),
    '''$explicit_copies
pick=(xs:array<int64> flag:bool):>array<int64>=>{
 const values:array<int64>=if flag xs else [42]
 return values
}''',
]

@pytest.mark.parametrize('source', CASES)
def test_array_selection_view(tmp_path, source):
    execute(tmp_path, 'array-selection', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_array_selection_retains_ownership_obligations(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_array_selection_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
