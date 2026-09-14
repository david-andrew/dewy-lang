"""Array snapshot fallbacks are shared across callers, including wide unions."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def source():
    classes = '\n'.join(f'Node{i}=type of [value:int64 items:array<int64>]' for i in range(12))
    choice = '|'.join(f'Node{i}' for i in range(12))
    functions = '\n'.join(f'''
change{i}=(nodes:array<Node>):>int64=>{{
    let copied=nodes
    if copied.length =? 0 return 0
    copied[0]=Node{i % 12}[99 [7 8]]
    return nodes.length
}}''' for i in range(24))
    calls = '+'.join(f'change{i}(nodes)' for i in range(24))
    return f'''{classes}
Node:type={choice}
{functions}
exercise=():>bool=>{{
    let nodes:array<Node>=[Node0[20 [1 2]] Node1[22 [3 4]]]
    let total={calls}
    if nodes.length not=? 2 return false
    let first=nodes[0]
    if first isnt? Node0 return false
    return total =? 48 and first.value =? 20
}}
main=():>int64=>{{
    if not exercise() return 1
    let before:int64=_arena_live_bytes
    loop i in 0.. and i <? 32 {{if not exercise() return 2}}
    if _arena_live_bytes not=? before return 3
    return 42
}}
'''


def test_array_helpers_preserve_independence_and_reclamation(tmp_path):
    code = codegen(SrcFile(None, source()), debug_locations=False)
    # Include every caller and all reachable runtime helpers in the budget.
    # Array-copy fallbacks first fell from 946,621 to 729,334 bytes. Sharing
    # release and union-copy dispatch, plus static literals, reaches 309,077.
    assert len(code.encode()) < 400_000
    output = tmp_path / 'shared-array-helpers.udewy'
    output.write_text(code)
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                text=True, timeout=15, check=False)
        assert result.returncode == 42, result.stdout + result.stderr


def test_replacing_optional_cells_preserves_aliases_and_pinned_storage(tmp_path):
    text = '''
exercise=():>bool=>{
    let values:array<int64|none>=[42 none]
    let copy=values
    if copy.length not=? 2 return false
    copy[0]=copy[0]
    copy[1]=17
    copy[0]=none
    if values.length not=? 2 return false
    let original=values[0]
    let retained=copy[1]
    return original isnt? none and original =? 42 and retained isnt? none and retained =? 17
}
main=():>int64=>{
    if not exercise() return 1
    let before:int64=_arena_live_bytes
    loop i in 0.. and i <? 64 {if not exercise() return 2}
    if _arena_live_bytes not=? before return 3
    let values:array<int64|none>=[42 none]
    let raw:int64=values transmute int64
    let previous:int64=__load_i64__(__load_i64__(raw))
    if values.length =? 0 return 4
    values[0]=7
    # Reuse of a released cell would overwrite the saved payload here.
    let other:array<int64|none>=[11 12]
    if __load_i64__(previous+8) not=? 42 return 5
    return 42
}
'''
    output = tmp_path / 'replace-optional-cells.udewy'
    output.write_text(codegen(SrcFile(None, text), debug_locations=False))
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                text=True, timeout=15, check=False)
        assert result.returncode == 42, result.stdout + result.stderr


def test_replacing_records_reclaims_roots_and_descendant_fields(tmp_path):
    text = (Path(__file__).resolve().parents[1] / 'fixtures/native_record_array_replacement.dewy').read_text()
    output = tmp_path / 'replace-records.udewy'
    output.write_text(codegen(SrcFile(None, text), debug_locations=False))
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                text=True, timeout=15, check=False)
        assert result.returncode == 42, result.stdout + result.stderr
