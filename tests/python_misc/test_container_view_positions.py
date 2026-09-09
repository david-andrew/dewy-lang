"""Compacting a container keeps membership, but moves remembered slots."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_views_expire_positions_before_compacting_live_entries(tmp_path):
    source = '''
let main=():>int64 => {
    let d=['a' -> 1 'b' -> 2 'c' -> 3]
    d.pop('a');
    let values=d.values
    printl(d['b'])
    printl(values.length)
    let e=['a' -> 1 'b' -> 2 'c' -> 3]
    let k:string='b'
    if k in? e {
        e.pop('a');
        if k in? e {
            let keys=e.keys
            printl(e[k])
            printl(keys.length)
        }
    }
    return 0
}
'''
    output = tmp_path / 'container_views.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['2', '2', '2', '2']


def test_const_container_captures_keep_membership_without_caller_slots(tmp_path):
    source = '''
let seed=['a' -> 1 'b' -> 2 'c' -> 3]
seed.pop('a');
const saved=seed
let read=():>int64 => saved['b']
let view=():>void => {let values=saved.values}
let main=():>int64 => {
    printl(read())
    view()
    printl(read())
    return 0
}
'''
    output = tmp_path / 'captured_views.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['2', '2']
