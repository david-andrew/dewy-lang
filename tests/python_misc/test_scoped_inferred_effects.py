"""Inferred callback rows retain their callee parameter scope at calls."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''read=(@value:int64):>int64=>value
other=(@value:int64):>int64=>value
forward=(ignored:int64 @target:int64):>int64 & reads<target>=>{
    let f=@read
    f=@other
    return f(@target)
}
main=():>int64=>{let value:int64=42 return forward(0 @value)}''',
    '''read=(@value:int64):>int64=>value
write=(@value:int64):>int64=>{value+=1 return value}
forward=(ignored:int64 @target:int64):>int64 & reads<target> & mutates<target>=>{
    let f=@read
    f=@write
    return f(@target)
}
main=():>int64=>{let value:int64=41 return forward(0 @value)}''',
    '''Box:type=[value:int64]
read=(@value:int64):>int64=>value
forward=(@box:Box ignored:int64):>int64 & reads<box.value>=>{
    let f=@read
    f=@read
    return f(@box.value)
}
main=():>int64=>{let box=Box[42] return forward(@box 0)}''',
    '''read=(@value:int64):>int64=>value
forward=(ignored:int64 @target:int64):>int64=>{
    let f=@read
    f=@read
    return f(@target)
}
outer=(@target:int64):>int64 & reads<target>=>forward(0 @target)
main=():>int64=>{let value:int64=42 return outer(@value)}''',
]
CASES += [
    """combine=(@first:int64 @second:int64):>int64=>{first+=second return first}
forward=(@left:int64 @right:int64):>int64 & reads<left> & reads<right> & mutates<right>=>{
    let f=@combine
    f=@combine
    return f(second=@left first=@right)
}
main=():>int64=>{let a:int64=2 let b:int64=40 return forward(@a @b)}""",
    """Inner:type=[value:int64]
Outer:type=[inner:Inner]
read=(@value:int64):>int64=>value
middle=(f:(@value:int64):>int64 & no mutates<value> @item:Inner):>int64=>f(@item.value)
outer=(@tree:Outer f:(@value:int64):>int64 & no mutates<value>):>int64 & no mutates<tree.inner.value>=>middle(@f @tree.inner)
main=():>int64=>{let tree=Outer[Inner[42]] return outer(@tree @read)}""",
]
ERRORS = [CASES[1].replace(' & mutates<target>', ''),
          CASES[0].replace(' & reads<target>', ' & no_effects'),
          CASES[2].replace('reads<box.value>', 'no reads<box.value>'),
          CASES[4].replace('mutates<right>', 'mutates<left>'),
          CASES[5].replace('no mutates<tree.inner.value>', 'no mutates<tree.inner>')]

@pytest.mark.parametrize('source', CASES)
def test_scoped_inferred_callback_executes(source, tmp_path):
    execute(tmp_path, 'scoped-inferred-effects', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_scoped_inferred_callback_retains_writes(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_native_scoped_inferred_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
