"""Type alternatives belong to stable elements until their storage changes."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HEADER='Box:type=[value:int64]\nChoice:type=Box|string|none\n'
CASES=[HEADER+body for body in [
'''main=():>int64=>{let xs:array<Choice>=[Box[42]]
if xs[0] is? Box return xs[0].value return 1}''',
'''main=():>int64=>{let xs:array<Choice>=[Box[42]]
const i=0 if xs[i] isnt? Box return 1 return xs[i].value}''',
'''main=():>int64=>{let xs:array<Choice>=[Box[1]]
if xs[0] is? Box {xs[0]=none}
xs[0]=Box[42] if xs[0] is? Box return xs[0].value return 1}''',
'''main=():>int64=>{let xs:array<Choice>=[Box[1]]
if xs[0] is? Box {xs[0].value=42 return xs[0].value} return 1}''',
'''main=():>int64=>{let values:totaldict<("a"|"b") Choice>=["a"->Box[42] "b"->none]
if values["a"] is? Box return values["a"].value return 1}''',
'''main=():>int64=>{let values:totaldict<("a"|"b") Choice>=["a"->Box[42] "b"->none]
const key="a" if values[key] isnt? Box return 1 return values[key].value}''',
'''main=():>int64=>{let xs:array<Box|none>=[Box[42]]
if xs[0] isnt? none return xs[0].value return 1}''',
]]
ERRORS=[HEADER+body for body in [
'''main=():>int64=>{let xs:array<Choice>=[Box[42]]
if xs[0] is? Box {xs[0]=none return xs[0].value} return 1}''',
'''main=():>int64=>{let xs:array<Choice>=[Box[42]]
const i=0 if xs[i] is? Box {xs[0]=none return xs[i].value} return 1}''',
'''change=(@xs:array<Choice>):>void=>{xs[0]=none}
main=():>int64=>{let xs:array<Choice>=[Box[42]]
if xs[0] is? Box {change(@xs) return xs[0].value} return 1}''',
'''main=():>int64=>{let values:totaldict<("a"|"b") Choice>=["a"->Box[42] "b"->none]
if values["a"] is? Box {values["a"]=none return values["a"].value} return 1}''',
'''main=():>int64=>{let values:totaldict<("a"|"b") Choice>=["a"->Box[42] "b"->none]
const key="a" if values[key] is? Box {values["a"]=none return values[key].value} return 1}''',
]]

CASES += [HEADER+body for body in [
'''choose=():>int64=>0
main=():>int64=>{let xs:array<Choice>=[Box[42]]
const i=choose() $runtime_assert i>=?0 and i<?xs.length
if xs[i] is? Box return xs[i].value return 1}''',
'''fill=(@x:Choice):>void=>{x=Box[42]}
main=():>int64=>{let xs:array<Choice>=[Box[1]]
if xs[0] is? Box {fill(@xs[0])}
if xs[0] is? Box return xs[0].value return 1}''',
'''main=():>int64=>{let values:dict<string Choice>=["a"->Box[1]]
$runtime_assert "a" in? values
if values["a"] is? Box {values.pop("a");}
values["a"]=Box[42]
if values["a"] is? Box return values["a"].value return 1}''',
]]
ERRORS += [HEADER+body for body in [
'''choose=():>int64=>0
main=():>int64=>{let xs:array<Choice>=[Box[42]]
const i=choose() $runtime_assert i>=?0 and i<?xs.length
if xs[i] is? Box {xs[0]=none return xs[i].value} return 1}''',
'''Holder:type=[choice:Choice]
main=():>int64=>{let xs:array<Holder>=[Holder[Box[42]]]
if xs[0].choice is? Box {xs[0].choice=none return xs[0].choice.value} return 1}''',
'''main=():>int64=>{let xs:array<Choice>=[Box[42]]
if xs[0] is? Box {xs.clear() xs.push(none) return xs[0].value} return 1}''',
]]

CASES += [HEADER+body for body in [
'''is_box=(x:Choice):>x is? Box=>x is? Box
main=():>int64=>{let xs:array<Choice>=[Box[42]]
if is_box(xs[0]) return xs[0].value return 1}''',
'''is_box=(x:Choice):>x is? Box=>x is? Box
main=():>int64=>{let values:totaldict<"a" Choice>=["a"->Box[42]]
if is_box(values["a"]) return values["a"].value return 1}''',
]]

CASES += [HEADER+'''Holder:type=[values:totaldict<"a" Choice>]
main=():>int64=>{let h=Holder[["a"->Box[42]]]
if h.values["a"] is? Box return h.values["a"].value return 1}''']
ERRORS += [HEADER+body for body in [
'''Holder:type=[values:totaldict<"a" Choice>]
main=():>int64=>{let h=Holder[["a"->Box[42]]]
if h.values["a"] is? Box {h.values["a"]=none return h.values["a"].value} return 1}''',
'''choose=():>int64=>0
main=():>int64=>{let xs:array<array<Choice>>=[[Box[42]]]
let i=choose() $runtime_assert i>=?0 and i<?xs.length
if xs[0][0] is? Box {xs[i].clear() xs[0].push(none) return xs[0][0].value} return 1}''',
]]

CASES += [HEADER+'''choose=():>int64=>0
main=():>int64=>{let xs:array<array<Choice>>=[[Box[42]]]
let i=choose() $runtime_assert i>=?0 and i<?xs.length
if xs[0][0] is? Box {let answer=xs[0][0].value xs[i].clear() return answer} return 1}''']

@pytest.mark.parametrize('source', CASES)
def test_indexed_type_fact(source,tmp_path):
    execute(tmp_path,'indexed-fact',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source', ERRORS)
def test_indexed_type_fact_invalidated(source):
    with pytest.raises(ReportException): codegen(SrcFile(None,source))

def test_native_indexed_type_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
