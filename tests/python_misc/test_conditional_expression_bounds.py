"""A value flow carries its interval and side effects through an expression boundary."""

import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_conditional_call_arguments_and_value_blocks_keep_bounds(tmp_path):
    source = '''
let take = (n:addr):>addr => n
let tick = ():>addr => { printl('tick') return 2 }
let choose = (flag:bool):>addr => take(if flag tick() else tick())
let block = ():>addr => take({ let n:addr=3 n })
let main = ():>int64 => {
    printl(choose(true))
    printl(choose(false))
    printl(block())
    return 0
}
'''
    output = tmp_path / 'conditional_bounds.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['tick', '2', 'tick', '2', '3']


@pytest.mark.parametrize('source', [
    '''let take = (n:addr):>addr => n
let bad = (flag:bool):>addr => take(if flag 1 else -1)''',
    '''let clear = (@xs:array<int64>):>bool => { xs.clear return true }
let take = (n:addr):>addr => n
let bad = (flag:bool):>int64 => {
    let xs:array<int64> = [7]
    take(if flag { xs.clear 1 } else 2);
    return xs[0]
}''',
    '''let clear = (@xs:array<int64>):>bool => { xs.clear return true }
let bad = (flag:bool):>int64 => {
    let xs:array<int64> = [7]
    let result = flag and clear(@xs)
    return xs[0]
}''',
    '''let clear = (@xs:array<int64>):>bool => { xs.clear return true }
let take = (n:addr):>addr => n
let bad = ():>int64 => {
    let xs:array<int64> = [7]
    take(if clear(@xs) 1 else 2);
    return xs[0]
}''',
])
def test_conditional_value_proofs_do_not_hide_a_bad_arm_or_mutation(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))
