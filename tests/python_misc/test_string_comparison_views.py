"""String comparisons borrow stable roots and snapshot before later writes."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/string_comparison_views.dewy').read_text()
# Hosted slice descriptors have a separate frame-region placement policy.
CASES = [SOURCE.replace('    if _arena_allocated_bytes not=?before return 6\n', ''),
    """let text:string='before'
change=():>string=>{text='after' return 'before'}
main=():>int64=>{let equal=text=?change() return if equal and text=?'after' 42 else 1}""",
    """let text:string='before'
change=():>string=>{text='after' return 'before'}
wrapped=():>string=>change()
main=():>int64=>{let equal=text=?wrapped() return if equal and text=?'after' 42 else 1}""",
    """change=(@text:string):>string=>{text='after' return 'before'}
main=():>int64=>{let text:string='before' let equal=text=?change(@text)
return if equal and text=?'after' 42 else 1}""",
    """Box:type=[text:string]
change=(@box:Box):>string=>{box.text='after' return 'before'}
main=():>int64=>{let box=Box['before'] let equal=box.text=?change(@box)
return if equal and box.text=?'after' 42 else 1}""",
    """change=(@text:string):>void=>{text='after'}
work=(early:bool):>int64=>{
    let text:string='before'
    let equal=text=?{change(@text) if early return 42 'before'}
    return if equal 42 else 1
}
main=():>int64=>{
    if work(false) not=?42 or work(true) not=?42 return 2
    let before:int64=_arena_live_bytes
    loop i in 0.. and i<?100 {if work(false) not=?42 or work(true) not=?42 return 3}
    return if _arena_live_bytes=?before 42 else 4
}""",
    """let text:string='before'
change=():>string=>{text='after' return 'before'}
let equal=text=?change()
main=():>int64=>if equal and text=?'after' 42 else 1""",
    """let text:string='before'
change=():>string=>{text='after' return 'before'}
read=(equal:bool=text=?change()):>int64=>if equal 42 else 1
main=():>int64=>read()""",
]


@pytest.mark.parametrize('source', CASES)
def test_string_comparisons_preserve_operand_values(source, tmp_path):
    execute(tmp_path, 'string-comparison-views', codegen(SrcFile(None, source)))


def test_native_string_comparison_views(tmp_path):
    import subprocess
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    binary = build_program_driver(tmp_path)
    check_structural_text(binary, tmp_path, cases=CASES, errors=[])
    source = tmp_path / 'native-budget.dewy'
    source.write_text(SOURCE)
    compiled = subprocess.run([binary, source, ROOT / 'library', tmp_path / 'prelude-cache'],
                              capture_output=True, text=True, timeout=120)
    assert compiled.returncode == 0, compiled.stderr
    execute(tmp_path, 'native-comparison-budget', compiled.stdout)
