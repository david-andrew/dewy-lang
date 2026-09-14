"""Optional dictionary elements preserve their cell and independent payload."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_get_copies_already_optional_object(tmp_path, target):
    source = tmp_path / 'optional-dict.dewy'
    source.write_text('''
Entry:type=[value:int64]
let read=(values:dict<int64 Entry|none> key:int64):>Entry|none=>values.get(key)
let main=():>int64=>{
    let values:dict<int64 Entry|none>=[1->Entry[42] 2->none]
    let selected=read(values 1)
    if selected is? none return 1
    if selected.value not=?42 return 2
    selected.value=99
    let again=read(values 1)
    if again is? none or again.value not=?42 return 3
    if read(values 2) isnt? none or read(values 3) isnt? none return 4
    return 42
}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr
