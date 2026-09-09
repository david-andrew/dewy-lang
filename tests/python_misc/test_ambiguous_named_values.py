"""A shared named-argument form survives ambiguities inside its value."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_named_values_keep_their_binding_form(tmp_path):
    source = '''
let Item:type = [value:int64]
let make = ():>Item => { printl('make') return Item[9] }
let take = (value:int64):>int64 => value
let default = (value:int64=make().value):>int64 => value
let main = ():>int64 => {
    printl(take(value=make().value))
    let constructed = Item[value=make().value]
    printl(constructed.value)
    let literal = [value=make().value]
    printl(literal.value)
    printl(default())
    return 0
}
'''
    output = tmp_path / 'named_values.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['make', '9'] * 4
