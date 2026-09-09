"""Changing array contents preserves its tag, but retains its store contract."""

import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import TypeCheckError, UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_narrowed_array_grows_in_a_loop_and_keeps_its_payload(tmp_path):
    source = SrcFile(None, '''
let make = (present:bool):>array<int64>|none => if present [1] else none
let main = ():>int64 => {
    let xs = make(true)
    if xs is? none return 99
    loop item in [2 3] { xs.push(item) }
    xs.push(4)
    let total:int64 = 0
    loop item in xs { total += item }
    return total
}
''')
    output = tmp_path / 'narrowed_array.udewy'
    output.write_text(codegen(source))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 10, result.stderr


def test_a_loop_store_still_invalidates_the_array_alternative():
    with pytest.raises((TypeCheckError, UserError)):
        check._typecheck_module(SrcFile(None, '''
let f = (input:array<int64>|none):>void => {
    let xs = input
    if xs is? none return
    loop item in [1 2] { xs.push(item) xs = none }
}
'''))


def test_a_place_argument_can_replace_the_optional_array():
    with pytest.raises((TypeCheckError, UserError)):
        check._typecheck_module(SrcFile(None, '''
let replace = (@xs:array<int64>|none):>void => { xs = none }
let f = (input:array<int64>|none):>void => {
    let xs = input
    if xs is? none return
    loop item in [1 2] { xs.push(item) replace(@xs) }
}
'''))


@pytest.mark.parametrize('contract, operation', [('length >=? 1', 'clear'), ('length <=? 0', 'push(1)')])
def test_optional_array_alternative_keeps_its_length_contract(contract, operation):
    with pytest.raises(UserError, match='keeps its declared length'):
        codegen(SrcFile(None, f'''
let f = (xs:array<int64 {contract}>|none):>void => {{
    if xs is? none return
    xs.{operation}
}}
'''))


def test_an_optional_exact_array_cannot_grow():
    with pytest.raises(UserError, match='exact-length arrays cannot change length'):
        check._typecheck_module(SrcFile(None, '''
let f = (xs:array<int64 length=1>|none):>void => {
    if xs is? none return
    xs.push(1)
}
'''))
