"""Early prelude generics use the concrete compilation's numeric helpers."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_bigint_equality_in_early_prelude_generic(tmp_path):
    source = '''
# Caller locals must not replace compiler-selected helpers inside a generic.
let _bigint_eq = (a:int64 b:int64):>bool => false
let main = ():>int64 => {
    let values:array<bigint> = [-3 0 184467440737095516170]
    if 184467440737095516170 in? values printl('large')
    if -3 in? values printl('negative')
    if 7 not in? values printl('absent')
    return 0
}
'''
    output = tmp_path / 'generic_numeric.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['large', 'negative', 'absent']
