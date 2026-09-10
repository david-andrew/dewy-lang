"""Conversion overloads keep their own bodies and parameter signatures."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize(('declaration', 'child'), [
    ('Point:type=', False),
    ('Point=type of ', False),
    ('Point=type of ', True),
])
def test_conversion_overloads_execute_the_body_for_the_selected_target(tmp_path, declaration, child):
    source = declaration + '''[
    x:int64
    __as__=():>string=>"point"
    __as__ &= ():>int64=>x+100
]
''' + ('let Child=type of Point\n' if child else '') + '''let main=():>int64=>{
    let point=CONSTRUCTOR[7]
    printl(point as string)
    printl(point as int64)
    return 0
}
'''
    source = source.replace('CONSTRUCTOR', 'Child' if child else 'Point')
    output = tmp_path / 'conversion_bodies.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'point\n107\n'
