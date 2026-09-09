"""A contextual optional flow constructs a cell even when both arms are present."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_optional_flow_arguments_keep_their_tagged_representation(tmp_path):
    source = '''
let number = (value:int64?=none):>int64 => {
    if value is? none return -1
    return value
}
let word = (value:string?):>string => {
    if value is? none return 'absent'
    return value
}
let choose = (flag:bool):>void => {
    printl(number(value=if flag 11 else 17))
    printl(number(value=if flag 23 else none))
    printl(word(if flag 'first' else 'second'))
    printl(word(if flag none else 'last'))
}
let main = ():>int64 => { choose(true) choose(false) return 0 }
'''
    output = tmp_path / 'optional_flow.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['11', '23', 'first', 'absent', '17', '-1', 'second', 'last']
