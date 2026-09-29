"""A place parameter may name an owner reached through an ambient call."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

PREFIX = """let table:dict<string int64>=['x'->0]
clear=():>void=>table.clear
relay=():>void=>clear()
"""
ERRORS = [
    PREFIX + f"""forward=(@input:dict<string int64>):>int64=>{{
if 'x' in? input {{let entry=@input['x'] {call}() entry=42 return entry}}
return 1}}
main=():>int64=>forward(@table)"""
    for call in ('clear', 'relay')
] + [
    PREFIX + """main=():>int64=>{
if 'x' in? table {let entry=@table['x'] relay() entry=42 return entry} return 1}""",
    """let values:array<int64>=[0]
clear=():>void=>values.clear
forward=(@input:array<int64>):>int64=>{
if input.length>?0 {let entry=@input[0] clear() entry=42 return entry} return 1}
main=():>int64=>forward(@values)""",
]
CASES = [
    PREFIX + """forward=(@input:dict<string int64>):>int64=>{
if 'x' in? input {let entry=@input['x'] entry=42
let answer=entry relay() return answer} return 1}
main=():>int64=>forward(@table)""",
    PREFIX + """main=():>int64=>{let own:dict<string int64>=['x'->0]
let entry=@own['x'] relay() entry=42 return entry}""",
    """private=():>void=>{let own:dict<string int64>=['x'->0] own.clear}
forward=(@input:dict<string int64>):>int64=>{
if 'x' in? input {let entry=@input['x'] private() entry=42 return entry} return 1}
main=():>int64=>{let table:dict<string int64>=['x'->0] return forward(@table)}""",
]

@pytest.mark.parametrize('source', ERRORS)
def test_ambient_alias_cannot_invalidate_live_place(source):
    with pytest.raises(ReportException, match='place.*(lifetime|conflicts)'):
        codegen(SrcFile(None, source), debug_locations=False)

@pytest.mark.parametrize('source', CASES)
def test_independent_owners_and_dead_places_allow_ambient_writes(tmp_path, source):
    execute(tmp_path, 'local-place-ambient', codegen(SrcFile(None, source), debug_locations=False))

def test_native_local_place_ambient_aliases(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
