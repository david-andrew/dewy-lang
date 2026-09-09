"""Bigint's existing decimal formatter serves retained strings as well as print."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_bigint_string_conversion_and_optional_members(tmp_path):
    source = '''
let visits:int64=0
let number=():>bigint => {visits+=1 return -123456789000000000001234567890}
let text=(n:[value:bigint?]):>string => if n.value is? none 'absent' else "{n.value}"
let optional=(n:bigint?):>string => "value={n}"
let main=():>int64 => {
    let retained="once:{number()}"
    printl(retained)
    printl(visits)
    printl(text([value=123456789000000000001234567890]))
    printl(text([value=0]))
    printl(text([value=none]))
    printl(optional(none))
    printl(optional(-9))
    let b:bigint=1000000000000000000
    printl(b as string)
    let xs:array<bigint>=[0 b]
    printl(xs as string)
    printl(retained)
    return 0
}
'''
    output = tmp_path / 'bigint_strings.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        'once:-123456789000000000001234567890', '1',
        '123456789000000000001234567890', '0', 'absent',
        'value=none', 'value=-9', '1000000000000000000',
        '[0 1000000000000000000]', 'once:-123456789000000000001234567890',
    ]
