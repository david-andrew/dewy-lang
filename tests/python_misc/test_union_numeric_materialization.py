"""Union destinations must materialize numeric payloads, evaluating once."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_optional_word_materializes_into_optional_bigint(tmp_path):
    source = '''
let calls:int64=0
let source=(n:uint64?):>uint64? => {calls+=1 return n}
let convert=(n:uint64?):>bigint? => {
    let count:bigint?=none
    count=source(n)
    return count
}
let direct=(n:int64):>bigint? => n
let main=():>int64 => {
    let a=convert(18446744073709551615)
    let b=convert(none)
    let z=convert(0)
    if a isnt? none {printl(a =? 18446744073709551615)}
    printl(b is? none)
    if z isnt? none {printl(z =? 0)}
    let d=direct(-9)
    if d isnt? none {printl(d =? -9)}
    printl(calls)
    return 0
}
'''
    output = tmp_path / 'union_conversion.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['true', 'true', 'true', 'true', '3']
