"""String results and place stores must outlive their source frame regions."""
from pathlib import Path
import re

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute


REBOUND = '''
make=(n:int64):>string=>"value:{n}"
replace=(text:string):>string=>{text=make(12345) return text}
fill=(@text:string):>void=>{text=make(12345)}
through=(text:string):>string=>{fill(@text) return "<{text}>"}
main=():>int64=>{
    if replace('x') not=? 'value:12345' return 1
    let text='x' as string
    fill(@text)
    if text not=? 'value:12345' return 2
    if through('x') not=? '<value:12345>' return 3
    return 42
}
'''


def clear_released_regions(code: str) -> str:
    """Reclaim bytes immediately, exposing reads masked by free-list reuse.

    Instrument emitted test code, without changing the library or relying on
    a later allocation to happen to reuse a particular chunk.
    """
    match = re.search(r'^let (\w+_region_release) =', code, re.MULTILINE)
    assert match is not None
    release = match.group(1)
    code = code.replace(release + '(', '__test_clear_region(')
    return code + f'''
let __test_clear_region = (region:int):>void => {{
    let chunk:int=__load_i64__(region+16)
    loop chunk not=? 0 {{
        let next:int=__load_i64__(chunk)
        let end:int=chunk+__load_i64__(chunk+8)
        let cursor:int=chunk+16
        loop cursor <? end {{__store_i64__(0 cursor) cursor+=8}}
        chunk=next
    }}
    {release}(region)
    return void
}}
'''


@pytest.mark.parametrize('source', ['rebound', 'existing_lifetimes'])
def test_no_string_reads_after_region_release(tmp_path, source):
    if source == 'rebound':
        text = REBOUND
    else:
        fixture = Path(__file__).resolve().parents[1] / 'fixtures/native_string_lifetimes.dewy'
        # Like test_string_scratch, check values here. Hosted placement has
        # a separate retention model from the native fixture's byte budget.
        text = fixture.read_text().replace('let main=', 'let retention_check=')
        text += '\nmain=():>int64=>if repeated() 42 else 1\n'
    emitted = codegen(SrcFile(None, text), debug_locations=False)
    execute(tmp_path, source, clear_released_regions(emitted))
