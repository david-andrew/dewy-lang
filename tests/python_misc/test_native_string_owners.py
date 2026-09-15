"""Native string backing survives views and returns to the arena exactly once."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point
from test_bootstrap_lowering import ARENA


@pytest.mark.parametrize('target', ['x86_64', 'c'])
@pytest.mark.parametrize('shared', [False, True])
def test_native_string_owners(tmp_path, target, shared):
    source = ARENA + '''
let main=():>int64=>{
    let before=_arena_live_bytes
    loop i in 0.. and i <? 512 {
        let data=_arena_alloc(0)
        let boundaries=_arena_alloc(4)
        __store_u32__(0 boundaries)
        let owner=_native_string_owner(data 0 boundaries 4)
        let value=_arena_alloc(48)
        __store_i64__(data value)
        __store_i64__(boundaries value+16)
        __store_i64__(owner value+40)
        let copy=_native_string_copy(value)
        let view=_arena_alloc(48)
        __store_i64__(_native_string_view_owner(copy) view+40)
        _native_string_release(value)
        _native_string_release(copy)
        if __load_i64__(owner) not=? 1 return 1
        if __load_u32__(boundaries) not=? 0 return 2
        _native_string_release(view)
    }
    if _arena_live_bytes not=? before return 3
    let literal=__static_alloca__(48)
    __store_i64__(0 literal+40)
    if _native_string_copy(literal) not=? literal return 4
    let view=_arena_alloc(48)
    __store_i64__(_native_string_view_owner(literal) view+40)
    _native_string_release(literal)
    _native_string_release(view)
    if _arena_live_bytes not=? before return 5
    let pinned=_arena_alloc(48)
    let owner=_native_string_owner(0 0 0 0)
    __store_i64__(owner pinned+40)
    _native_string_pin(pinned);
    let held=_arena_live_bytes
    _native_string_release(pinned)
    if _native_string_copy(pinned) not=? pinned return 6
    if _arena_live_bytes not=? held return 7
    return 42
}
'''
    if shared:
        # Substitute only the workload: leave the legacy runtime helpers
        # available so this also checks staged-seed compatibility.
        workload = source[len(ARENA):]
        workload = workload.replace('_arena_alloc(48)', '_native_string_descriptor()')
        workload = workload.replace('_native_string_copy(', '_native_string_retain(')
        workload = workload.replace('_native_string_release(', '_native_string_drop(')
        workload = workload.replace('let copy=_native_string_retain(value)', '''
        let allocated=_arena_allocated_bytes
        let copy=_native_string_retain(value)
        if copy not=? value return 8
        loop retain_index in 0.. and retain_index <? 1024 {
            let other=_native_string_retain(copy)
            if other not=? copy return 9
            _native_string_drop(other)
        }
        if _arena_allocated_bytes not=? allocated return 10
        ''')
        source = ARENA + workload
    input_file = tmp_path / 'owners.dewy'
    input_file.write_text(source)
    output = tmp_path / 'owners.udewy'
    output.write_text(codegen(SrcFile.from_path(input_file), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], timeout=10)
    assert result.returncode == 42
