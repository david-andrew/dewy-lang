"""Project a direct getter's scalar result without changing its call boundary."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.backend.udewy.lowering_objects import _ObjectLowering
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def execute(tmp_path, name, code, expected=42):
    path = tmp_path / f'{name}.udewy'
    path.write_text(code)
    results = []
    for target in ['x86_64', 'c']:
        assert entry_point(path, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(path).resolve()], capture_output=True,
                                text=True, timeout=15, check=False)
        assert result.returncode == expected, result.stdout + result.stderr
        results.append(result)
    return results


def test_scalar_getter_avoids_record_snapshot_allocations(tmp_path, monkeypatch):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/native_scalar_projection.dewy')
    optimized = codegen(source, debug_locations=False)
    with monkeypatch.context() as patch:
        patch.setattr(_ObjectLowering, '_scalar_getter_projection', lambda *_: None)
        baseline = codegen(source, debug_locations=False)
    for result in execute(tmp_path, 'projected', optimized):
        assert list(map(int, result.stdout.split())) == [0, 0, 0]
    for result in execute(tmp_path, 'copied', baseline):
        allocated, _copied, retained = map(int, result.stdout.split())
        assert allocated > 100_000  # Positive control: returning full records costs storage.
        assert retained == 0


def test_projection_preserves_effects_defaults_captures_and_dispatch(tmp_path):
    source = (ROOT / 'tests/fixtures/scalar_projection_effects.dewy').read_text()
    execute(tmp_path, 'effects', codegen(SrcFile(None, source), debug_locations=False))


def test_selected_aggregate_keeps_its_lifetime_without_copying_the_record(tmp_path, monkeypatch):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/aggregate_getter_projection.dewy')
    optimized = codegen(source, debug_locations=False)
    with monkeypatch.context() as patch:
        patch.setattr(_ObjectLowering, '_scalar_getter_projection', lambda *_: None)
        baseline = codegen(source, debug_locations=False)
    projected = execute(tmp_path, 'aggregate-projected', optimized)
    copied = execute(tmp_path, 'aggregate-copied', baseline)
    for fast, slow in zip(projected, copied):
        fast_allocated, fast_retained = map(int, fast.stdout.split())
        slow_allocated, slow_retained = map(int, slow.stdout.split())
        assert fast_retained == slow_retained == 0
        assert fast_allocated < slow_allocated // 2


def test_container_getter_preserves_the_complete_table_for_operations(tmp_path):
    source = '''
read=(table:dict<string int64>):>dict<string int64>=>table
main=():>int64=>{
    let table=['value' -> 42]
    if 'value' not in? read(table) return 1
    if read(table).get('value' 0) not=? 42 return 2
    let removed=read(table).pop('value' default=0)
    if removed is? none or removed not=? 42 return 3
    return table['value']
}
'''
    execute(tmp_path, 'container-getter', codegen(SrcFile(None, source), debug_locations=False))


def test_projected_field_of_a_temporary_element_is_retained_once(tmp_path):
    source = '''
Node:type=[text:string]
nodes=(text:string):>array<Node length=1>=>[Node["value:{text}"]]
read=(text:string):>Node=>nodes(text)[0]
exercise=():>int64=>{
    let text=read('42').text
    return if text =? 'value:42' 42 else 1
}
main=():>int64=>{
    if exercise() not=? 42 return 1
    let before:int64=_arena_live_bytes
    loop i in 0.. and i <? 100 {if exercise() not=? 42 return 2}
    if _arena_live_bytes not=? before return 3
    return 42
}
'''
    execute(tmp_path, 'temporary-element', codegen(SrcFile(None, source), debug_locations=False))


def test_projected_getter_keeps_runtime_guard(tmp_path):
    source = '''
Node=type of [value:int64]
node_at=(nodes:array<Node> id:addr):>Node=>{
    $runtime_assert id <? nodes.length
    return nodes[id]
}
main=():>int64=>{
    let nodes:array<Node>=[]
    return node_at(nodes 0).value
}
'''
    for result in execute(tmp_path, 'guard', codegen(SrcFile(None, source), debug_locations=False), 101):
        assert 'assertion' in result.stderr.lower()


def test_nested_scalar_getter_avoids_enclosing_record_copies(tmp_path, monkeypatch):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/nested_getter_projection.dewy')
    optimized = codegen(source, debug_locations=False)
    with monkeypatch.context() as patch:
        patch.setattr(_ObjectLowering, '_scalar_getter_projection', lambda *_: None)
        baseline = codegen(source, debug_locations=False)
    for result in execute(tmp_path, 'nested-projected', optimized):
        assert list(map(int, result.stdout.split())) == [0, 0, 0]
    for result in execute(tmp_path, 'nested-copied', baseline):
        allocated, _copied, retained = map(int, result.stdout.split())
        assert allocated > 100_000
        assert retained == 0


NESTED_EFFECTS = '''Inner:type=[value:int64 text:string]
Node:type=[left:Inner right:Inner]
let calls:int64=0
index=():>addr=>{calls+=1 return 0}
read=(nodes:array<Node> id:addr=index()):>Node=>{
    calls+=1
    $runtime_assert id<?nodes.length
    return nodes[id]
}
main=():>int64=>{
    let nodes:array<Node>=[Node[Inner[20 "left"] Inner[22 "right"]]]
    let a=read(nodes).left.value
    let b=read(nodes).right.value
    let text=read(nodes).right.text
    if calls not=?6 or text not=?"right" return 1
    return a+b
}'''

NESTED_TEMPORARY = '''Inner:type=[text:string items:array<int64>]
Node:type=[inner:Inner]
nodes=(text:string):>array<Node length=1>=>[Node[Inner["value:{text}" [40 2]]]]
read=(text:string):>Node=>nodes(text)[0]
exercise=():>int64=>{
    let text=read("42").inner.text
    let items=read("42").inner.items
    if text not=?"value:42" or items.length not=?2 return 1
    return items[0]+items[1]
}
main=():>int64=>{
    if exercise() not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in 0.. and i<?100 {if exercise() not=?42 return 2}
    if _arena_live_bytes not=?before return 3
    return 42
}'''


def test_nested_projection_keeps_effects_and_distinguishes_paths(tmp_path):
    execute(tmp_path, 'nested-effects', codegen(SrcFile(None, NESTED_EFFECTS)))


def test_nested_handles_outlive_their_temporary_owner(tmp_path):
    execute(tmp_path, 'nested-temporary', codegen(SrcFile(None, NESTED_TEMPORARY)))


def test_native_nested_getter_projections(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[(ROOT / 'tests/fixtures/nested_getter_projection.dewy').read_text(),
                                 NESTED_EFFECTS, NESTED_TEMPORARY], errors=[],
                          outputs=['0 0 0\n', '', ''])
    source = tmp_path / 'nested-guard.dewy'
    source.write_text(NESTED_GUARD)
    compiled = subprocess.run([build_program_driver(tmp_path), source, ROOT / 'library', tmp_path / 'guard-cache'],
                              capture_output=True, text=True, timeout=120)
    assert compiled.returncode == 0, compiled.stderr
    for result in execute(tmp_path, 'native-nested-guard', compiled.stdout, 101):
        assert 'assertion' in result.stderr.lower()


NESTED_GUARD = NESTED_EFFECTS.split('main=', 1)[0] + '''main=():>int64=>{
let nodes:array<Node>=[] return read(nodes).left.value
}'''


def test_nested_projection_keeps_its_runtime_guard(tmp_path):
    for result in execute(tmp_path, 'nested-guard', codegen(SrcFile(None, NESTED_GUARD)), 101):
        assert 'assertion' in result.stderr.lower()
