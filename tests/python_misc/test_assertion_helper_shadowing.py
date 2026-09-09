"""Generated assertion reporting references its library, not same-named locals."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_runtime_assertion_helpers_keep_their_binding_identity(tmp_path):
    source = '''
let ensure = (exit:int64):>void => {
    let Report = 9
    let _assertion_report = 3
    let _assertion_render = 4
    $runtime_assert exit >? 0
}
let main = ():>int64 => { ensure(0) return 0 }
'''
    output = tmp_path / 'assertion_helpers.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 101
    assert 'exit >? 0' in result.stderr
