"""Loop-iteration regions: iteration-local strings live in the loop's region, reset every iteration; escaping ones climb out."""
import re

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def _function(emitted: str, name: str) -> str:
    start = emitted.index(f'let {name} = ')
    end = emitted.find('\nlet ', start)
    return emitted[start:] if end == -1 else emitted[start:end]


SCAN = (
    'let scan = (text:string):>int64 => {\n'
    '    let total:int64 = 0\n'
    '    let i:int64 = 0\n'
    '    loop i <? 10 {\n'
    '        i += 1\n'
    '        if i =? 2 { continue }\n'
    '        let joined:string = text.split"-".join"+"\n'
    '        total += joined.length\n'
    '    }\n'
    '    return total\n'
    '}\n'
    'let main = ():>int64 => scan("a-b")\n'
)


def test_an_iteration_local_string_lives_in_the_loop_region_reset_every_iteration() -> None:
    scan = _function(_compile(SCAN), 'scan')
    region = re.search(r'let (__dewy_string_loop_region_\d+):int64 = \S+region_new\(\)', scan)
    assert region, scan
    name = region.group(1)
    assert re.search(rf'region_alloc\({name} ', scan)
    # reset before the `continue` and at the end of the body; released at the function's exit
    assert re.search(rf'region_reset\({name}\)\n\s*continue', scan)
    assert scan.count(f'region_reset({name})') == 2
    assert re.search(rf'region_release\({name}\)', scan)


def test_a_string_assigned_to_a_binding_outside_the_loop_climbs_to_the_function_region() -> None:
    source = SCAN.replace('    let total:int64 = 0\n', '    let total:int64 = 0\n    let last:string = ""\n').replace(
        '        total += joined.length\n', '        total += joined.length\n        last = joined\n')
    scan = _function(_compile(source), 'scan')
    assert 'loop_region' not in scan
    assert re.search(r'region_alloc\(__dewy_string_region_\d+ ', scan)
