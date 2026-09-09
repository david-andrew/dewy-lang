"""A lowered optional payload must not be unwrapped a second time by a consumer."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_narrowed_string_key_survives_dictionary_comparison_lowering(tmp_path):
    source = '''
let choose = (text:string present:bool):>string? => if present text else none
let probe = (text:string):>int64 => {
    let key = choose(text true)
    if key is? none return 1
    let values:dict<string int64> = ['first' -> 7 'second' -> 9]
    if key in? values printl(values[key])
    else printl('absent')
    let found = values.get(key)
    if found isnt? none printl(found)
    values[key] = 13
    printl(values[key])
    return 0
}
let main = ():>int64 => {
    probe('first');
    probe('second');
    probe('missing');
    return 0
}
'''
    output = tmp_path / 'string_keys.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['7', '7', '13', '9', '9', '13', 'absent', '13']
